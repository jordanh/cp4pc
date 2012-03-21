"""Encapsulate common higher-level elements common to many devices"""
from rci.model.base import BranchNode, RCIAttribute, TargetNode
import traceback


class DeviceRoot(BranchNode):

    def __init__(self):
        BranchNode.__init__(self, "/")

    def to_descriptor_xml(self, xml_query_node):
        return ''.join(x.to_descriptor_xml(None) for x in self)


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

    def handle_xml(self, xml_tree):
        """Handle xml under "query_descriptor" request and return a response"""
        if len(xml_tree) == 0:
            return self._xml_tag(self.device_tree.to_descriptor_xml(None))
        else:
            response = ""
            for subtree in xml_tree:
                match_root = self._tree_match(subtree, self.device_tree)
                if match_root is None:
                    response += ('<{tag}>{error}</{tag}>'
                                 .format(tag=subtree.tag,
                                         error=self._xml_error(1)))
                else:
                    # we need leaf node in XML, assume single child
                    xml_node = xml_tree
                    while len(xml_node.getchildren()) > 0:
                        xml_node = xml_node.getchildren()[0]

                    # get the descriptor, providing leaf xml as a helper
                    response += match_root.to_descriptor_xml(xml_node)
            return self._xml_tag(response)

#                try:
#                    xml_node = xml_tree
#                    while len(xml_node.getchildren()) > 0:
#                        xml_node = xml_tree.getchildren()[0]
#    
#                    # get the descriptor, providing leaf xml as a helper
#                    response += match_root.to_descriptor_xml(xml_node)
#                except Exception, e:
#                    response += ('<{tag}>{error}</{tag}>'
#                                 .format(tag=subtree.tag,
#                                         error=self._xml_error(1, hint=e)))
#            return self._xml_tag(response)


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

    def to_descriptor_xml(self, xml_query_node):
        """Get the descriptor XML for do_command

        It might be the case that we get an xml_query_node for a request
        that looks something like this::

            <rci_request>
                <query_descriptor>
                    <do_command target="file_system" />
                </query_descriptor>
            </rci_request>

        """
        #FIXME: we should only return attrs when no target is specified.
        if xml_query_node is None:
            return BranchNode.to_descriptor_xml(self, xml_query_node)
        target = xml_query_node.attrib.get('target', None)
        if target is None:
            return BranchNode.to_descriptor_xml(self, xml_query_node)
        
        target_node = self.get(target)
        if target_node is None:
            return self._xml_error(2) #name not registered

        return ('<descriptor element="do_command">'
                '{target}</descriptor>'
                .format(target=target_node.to_descriptor_xml(xml_query_node)))

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
