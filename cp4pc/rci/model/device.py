#
# Copyright (c) 2009-2012 Digi International Inc.
# All rights not expressly granted are reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at http://mozilla.org/MPL/2.0/.
#
# Digi International Inc. 11001 Bren Road East, Minnetonka, MN 55343
#
"""Encapsulate common higher-level elements common to many devices"""
from rci.model.base import BranchNode, RCIAttribute, TargetNode
import traceback


class DeviceRoot(BranchNode):
    
    desc = "Remote Command Interface request"
    
    def __init__(self):
        BranchNode.__init__(self, "rci_request")

    def descriptor_xml(self, xml_node):
        if not len(xml_node):
            return BranchNode.descriptor_xml(self, xml_node)
        else:
            return self.child_descriptors(xml_node)


class RciSettings(BranchNode):
    """Retrieve device configuration"""

    desc = "Retrieve device configuration"
    errors = {
      1: "Internal error (load failed)",
      2: "Internal error (save failed)",
      3: "Field specified does not exist",
    }

    def __init__(self):
        BranchNode.__init__(self, 'query_setting')


class RciState(BranchNode):
    """RCI query_state handler"""

    desc = "Query a device for its current state"

    def __init__(self):
        BranchNode.__init__(self, 'query_state')


class RciDescriptor(BranchNode):

    desc = "Query a device for its capabilities"
    errors = {
      1: "Field specified does not exist",
      2: "Field specified has no associated descriptor data"
    }

    def __init__(self, device_tree):
        BranchNode.__init__(self, "query_descriptor")
        self.device_tree = device_tree

    def handle_xml(self, xml_node):
        """Handle xml under "query_descriptor" request and return a response"""
        return self._xml_tag(self.device_tree.descriptor_xml(xml_node))

    def dscr_avail(self):
        return True

class RciDoCommand(BranchNode):
    desc = "Trigger some piece of functionality"

    errors = {
        1: "Application call failed",
        2: "Name not registered",
        3: "Unexpected error occurred",
        4: "Invalid response from python (call was performed)",
        5: "Request sent but timeout waiting for python response",
    }

    @property
    def attrs(self):
        """property for .attrs, as we want to calculate dynamically"""
        target_values = [RCIAttribute(target.name, target.desc) for target in self]
        return [RCIAttribute("target", "The target for the command to execute",
                             target_values)]

    def __init__(self):
        BranchNode.__init__(self, 'do_command')

    def add_callback(self, name, callback):
        """Add a simple target, descriptor know nothing about children"""
        target_node = self.get(name)
        if target_node is not None:
            raise ValueError("RCI target already registered: %s" % name)
        self.attach(TargetNode(name, '', callback))
        return self  # allow for method chaining

    def remove_callback(self, name):
        """Remove a target"""
        target_node = self.get(name)
        if target_node is not None:
            self.children.remove(target_node)
        return self # allow for method chaining

    def descriptor_xml(self, xml_node):
        """Get the descriptor XML for do_command

        It might be the case that we get an xml_query_node for a request
        that looks something like this::

            <rci_request>
                <query_descriptor>
                    <do_command target="file_system" />
                </query_descriptor>
            </rci_request>

        """
        children_xml = ''
        target = xml_node.attrib.get('target', None)
        if target is None:
            # remove children from xml_node, then get top level response from children
            for xml_child in list(xml_node):
                xml_node.remove(xml_child)
            for child_node in self:
                children_xml += child_node.descriptor_xml(xml_node)
        else:
            target_node = self.get(target)
            if target_node is None:
                return self._xml_error(2) #name not registered
        
            children_xml = target_node.descriptor_xml(xml_node)

        return ('<descriptor element="do_command">'
                '{target}</descriptor>'
                .format(target=children_xml))
        
    def handle_xml(self, xml_tree):
        target = xml_tree.attrib.get('target')
        if target is None:
            # no target attribute in XML
            return self._xml_tag(self._xml_eror(2))
        target_node = self.get(target)
        if target_node is None:
            # Target not registered
            return self._xml_tag(self._xml_error(2))
        # Have target handle request
        try:
            #NOTE: normally we would pass each of the children of xml_tree
            # can't do this here, since custom targets may not even have children.
            return self._xml_tag(target_node.handle_xml(xml_tree), attributes={'target': target})
        except:
            # wrap all errors, log to stderr locally
            traceback.print_exc()
            return self._xml_tag(self._xml_error(1))
