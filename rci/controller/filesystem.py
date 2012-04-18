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
from rci.model.base import BranchNode, TargetNode
import base64
import os


def _is_path_within_root(path):
    norm_path = os.path.normpath(path)
    if norm_path.startswith('..'):
        return False
    else:
        return True

def _path_to_fs(root, path):
    if path.startswith('/'):
        path = path[1:]
    return os.path.join(root, path)


class FileSystemTarget(TargetNode):
    desc = "Interact with a portion of the device filesystem"
    
    def __init__(self, root_fs="."):
        TargetNode.__init__(self, "file_system")
        # go ahead and include the FileSystem commands
        self.attach(FilesystemPutFile(root_fs))
        self.attach(FilesystemGetFile(root_fs))
        self.attach(FilesystemRemoveFile(root_fs))
        self.attach(FileystemListDirectory(root_fs))
        

class FilesystemPutFile(BranchNode):
    desc = "Put (upload) a file on the device"
    errors = {
        1: "No name specified",
        2: "No data specified",
        3: "Invalid data",
        4: "No path to specified name",
        5: "OSError when writing file to disk",
    }

    def __init__(self, root):
        BranchNode.__init__(self, 'put_file')
        self.root = root

    def handle_xml(self, put_file_element):
        # validate that name for deletion has been specified
        name = put_file_element.attrib.get('name', None)
        if name is None:
            return self._xml_error(1)
        if len(list(put_file_element)) != 1:
            return self._xml_error(2)

        # validate that the data tag exists
        data_element = list(put_file_element)[0]
        if data_element.tag != "data":
            return self._xml_error(2)

        # validate that data is valid base64
        try:
            decoded_data = base64.decodestring(data_element.text)
        except:
            return self._xml_error(3)
        
        # validate that the path is within the root path
        if not _is_path_within_root(name):
            return self._xml_error(3)

        # validate that the target directory exists
        path = _path_to_fs(self.root, name)
        dirname = os.path.dirname(path)
        if not os.path.exists(dirname) and os.path.isdir(path):
            self._xml_error(4)

        # try to write file
        try:
            with open(path, 'wb') as f:
                f.write(decoded_data)
        except OSError:
            return self._xml_error(5)
        else:
            return self._xml_tag(attributes={'name': name})


class FilesystemGetFile(BranchNode):

    desc = "Get (download) a file from the device"
    errors = {
        1: "No name specified for get_file",
        2: "File specified does not exist",
        3: "OS Error when attempting to read file"
    }

    def __init__(self, root):
        BranchNode.__init__(self, 'get_file')
        self.root = root

    def handle_xml(self, get_file_element):
        name = get_file_element.attrib.get('name', None)
        if name is None:
            return self._xml_error(1)

        # validate that the path is within the root path
        if not _is_path_within_root(name):
            return self._xml_error(3)

        path = _path_to_fs(self.root, name)
        if not (os.path.exists(path) and os.path.isfile(path)):
            return self._xml_error(2)
        try:
            with open(path) as f:
                data = ("<data>%s</data>" %
                        base64.encodestring(f.read()).strip())
                return self._xml_tag(body=data, attributes={'name': name})
        except OSError:
            return self._xml_error(3)


class FilesystemRemoveFile(BranchNode):

    desc = "Remove a file from the filesystem"
    errors = {
        1: "No name specified for deletion",
        2: "File does not exist",
        3: "Cannot remove directories",
        4: "Unknown filesystem error",
    }

    def __init__(self, root):
        BranchNode.__init__(self, 'rm')
        self.root = root

    def handle_xml(self, rm_file_element):
        name = rm_file_element.attrib.get('name', None)
        if name is None:
            return self._xml_error(1)

        # validate that the path is within the root path
        if not _is_path_within_root(name):
            return self._xml_error(3)

        path = _path_to_fs(self.root, name)
        if os.path.exists(path):
            if os.path.isdir(path):
                return self._xml_error(3)
            try:
                os.remove(path)
                return self._xml_tag(attributes={'name': name})
            except OSError:
                return self._xml_error(4)
        else:
            return self._xml_error(2)


class FileystemListDirectory(BranchNode):

    desc = "List the contents of a directory"

    def __init__(self, root):
        BranchNode.__init__(self, 'ls')
        self.root = root

    def handle_xml(self, ls_element):
        """List contents of some directory on the mounted file_system"""
        directory = ls_element.attrib.get('dir', None)
        if directory is None:
            directory = ls_element.attrib.get('path', None)
        if directory is None:
            return ("<{tag}><error id='1' "
                    "desc='No dir specified for ls' /></{tag}>"
                    .format(tag=ls_element.tag))

        # validate that the path is within the root path
        if not _is_path_within_root(directory):
            return self._xml_error(3)

        # there is a directory attribute, now we need to validate that
        # that directory actually exists on the filesystem
        # TODO: add hash support
        path = _path_to_fs(self.root, directory)
        if not os.path.isdir(path):
            return ('<error id="3"><desc>Listing failed</desc>'
                    '<hint>Unable to read directory</hint></error>')
        else:
            retval = ""
            for name in os.listdir(path):
                full_path = os.path.join(path, name)
                if os.path.isfile(full_path):
                    retval += ('<file name="{name}" size="{size}" />'
                               .format(name=name,
                                       size=os.path.getsize(full_path)))
                else:
                    retval += ('<dir name="{name}" />'
                               .format(name=name))
            return ('<ls dir="{directory}">{retval}</ls>'
                    .format(directory=directory, retval=retval))
