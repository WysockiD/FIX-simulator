import xml.etree.ElementTree as ET
import logging

logger = logging.getLogger(__name__)

class FixProtocol:

    def __init__(self, dictionary_path):
        self.path = dictionary_path
        self.fields_by_number = {}
        self.messages = {}
        try:
            self._load_dictionary()
        except FileNotFoundError:
            logger.critical(f"FIX dictionary file not found at: {dictionary_path}")
            raise
        except ET.ParseError as e:
            logger.critical(f"Error parsing FIX dictionary XML {dictionary_path}: {e}")
            raise

    def _load_dictionary(self):
        tree = ET.parse(self.path)
        root = tree.getroot()

        for field_node in root.findall('.//fields/field'):
            number = int(field_node.get('number'))
            self.fields_by_number[number] = {
                'name': field_node.get('name'),
                'type': field_node.get('type')
            }

        for msg_node in root.findall('.//messages/message'):
            msg_type = msg_node.get('msgtype')
            self.messages[msg_type] = {
                'name': msg_node.get('name'),
                'fields': {int(f.get('number')): {'required': f.get('required') == 'Y'} for f in msg_node.findall('field')}
            }

    def validate_message(self, fix_message):
        
        if 35 not in fix_message:
            return False, "Message is missing MsgType(35)"
        
        msg_type = fix_message.get(35).decode()
        if msg_type not in self.messages:
            return False, f"Unknown MsgType(35)='{msg_type}' in this protocol"

        required_fields = self.messages[msg_type]['fields']
        for field_num, attributes in required_fields.items():
            if attributes['required'] and field_num not in fix_message:
                field_name = self.fields_by_number.get(field_num, {}).get('name', 'Unknown')
                return False, f"Required field {field_name}({field_num}) missing from {self.messages[msg_type]['name']}"

        return True, "Message valid"

    def __str__(self):
        return f"<FixProtocol loaded from '{self.path}'>"