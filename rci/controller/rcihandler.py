"""Handlers for RCI data that map to rci tree structures"""
try:
    from xml.etree import cElementTree as ET
except:
    try:
        from xml.etree import ElementTree as ET
    except:
        import ElementTree as ET

class RCIHandler(object):
    """Manage the device tree and its mapping to rci requests"""

    def __init__(self, device_tree):
        self.device_tree = device_tree

    def _rci_response(self, body):
        return "<rci_reply version=\"1.1\">%s</rci_reply>" % body

    def add_callback(self, name, callback):
        do_command = self.device_tree.get('do_command')
        if do_command is None:
            raise Exception("do_command not supported")
        else:
            return do_command.add_callback(name, callback)
            
    def remove_callback(self, name):
        do_command = self.device_tree.get('do_command')
        if do_command:
            return do_command.remove_callback(name) 

    def handle_rci_request(self, xml_text):
        """Return RCI response based on our tree structure"""
        root = ET.fromstring(xml_text)
        # TODO: add logging statements

        return_xml = ""
        if not root.tag == "rci_request":
            return_xml = ('<error id="1" desc="Expected rci_request root'
                          ' node but got something else />')
        for xml_child in root:
            for device_node in self.device_tree:
                if device_node.name == xml_child.tag:
                    node_xml = device_node.handle_xml(xml_child)
                    break
            else:
                node_xml = ('<{tag}><error id="1" '
                            'desc="Unknown tag" /></{tag}>'
                               .format(tag=xml_child.tag))
            return_xml += node_xml

        return_xml = self._rci_response(return_xml)
        #TODO: add logging statement

        return return_xml
