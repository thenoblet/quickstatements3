import re

from .base import BaseParser
from .base import ParserException
from core.models import Batch
from core.models import BatchCommand


class V1CommandParser(BaseParser):

    CREATE_PROPERTY_ALLOWED_DATATYPES = [
        "commonsMedia",
        "globe-coordinate",
        "wikibase-item",
        "wikibase-property",
        "string",
        "monolingualtext",
        "external-id",
        "quantity",
        "time",
        "url",
        "math",
        "geo-shape",
        "musical-notation",
        "tabular-data",
        "wikibase-lexeme",
        "wikibase-form",
        "wikibase-sense",
    ]
    WHAT = {"L": "label", "D": "description", "A": "alias", "S": "sitelink"}

    def parse_create(self, elements):
        llen = len(elements)
        if llen != 1:
            raise ParserException("CREATE command can have only 1 column")
        else:
            return {"action": "create", "type": "item"}

    def parse_create_property(self, elements):
        llen = len(elements)
        if llen != 2:
            raise ParserException("CREATE PROPERTY command must have 2 columns")
        else:
            datatype = elements[1]
            if datatype not in self.CREATE_PROPERTY_ALLOWED_DATATYPES:
                raise ParserException(
                    f"CREATE PROPERTY datatype allowed values: {self.CREATE_PROPERTY_ALLOWED_DATATYPES}"
                )
            return {"action": "create", "type": "property", "data": datatype}

    def parse_merge(self, elements):
        llen = len(elements)
        if llen != 3:
            raise ParserException("MERGE command must have 3 columns")
        else:
            item1 = elements[1].strip()
            item2 = elements[2].strip()
            try:
                item1_id = int(item1[1:])
                item2_id = int(item2[1:])
                if item1_id > item2_id:
                    # Always merge into older item
                    item1, item2 = item2, item1
                return {"action": "merge", "type": "item", "item1": item1, "item2": item2}
            except ValueError:
                raise ParserException(f"MERGE items wrong format item1=[{item1}] item2=[{item2}]")

    def parse_statement_by_id(self, elements):
        llen = len(elements)
        if llen != 2:
            raise ParserException("remove statement by ID command must have 2 columns")
        else:
            _id = elements[1].strip()
            _split = _id.split("$")
            if len(_split) != 2:
                raise ParserException("ITEM ID format in REMOVE STATEMENT must be Q1234$UUID")
            return {"action": "remove", "what": "statement", "id": _id, "entity": {"id": _split[0]}}

    def parse_statement(self, elements, first_command):
        llen = len(elements)
        if llen < 3:
            raise ParserException("STATEMENT must contain at least entity, property and value")

        if first_command[0] == "-":
            action = "remove"
            entity = first_command[1:]
        else:
            action = "add"
            entity = first_command

        entity_type = self.get_entity_type(entity)

        if entity_type is None:
            raise ParserException(f"Invalid entity {entity}")

        vvalue = self.parse_value(elements[2])

        if llen == 3 and elements[1][0] in ["L", "A", "D", "S"]:
            # We are adding / removing a LABEL, ALIAS, DESCRIPTION or SITELINK to our property
            what = self.WHAT[elements[1][0]]
            if not vvalue or vvalue["type"] != "string":
                raise ParserException(f"{what} must be a string instance")

            lang = elements[1][1:]
            data = {"action": action, "what": what, "item": entity, "value": vvalue}
            if what == "sitelink":
                if vvalue["value"] == "":
                    data["action"] = "remove"
                data["site"] = lang
            else:
                data["language"] = lang

        else:
            # We are adding / removing values
            pproperty = elements[1]
            if not self.is_valid_property_id(pproperty):
                raise ParserException(f"Invalid property {pproperty}")

            data = {
                "action": action,
                "what": "statement",
                "entity": {"type": entity_type, "id": entity},
                "property": pproperty,
                "value": vvalue,
            }

            current_reference_block = []  # We can have multiple reference blocks
            references = [current_reference_block]
            has_references = False

            qualifiers = []

            # ITERATE OVER qualifiers or previous_references (key, value) pairs
            index = 3
            while index + 1 < llen:
                key = elements[index].strip()
                value = self.parse_value(elements[index + 1].strip())

                if key[0] == "P":  # PROPERTIES
                    if not self.is_valid_property_id(key):
                        raise ParserException(f"Invalid qualifier property {key}")
                    qualifiers.append({"property": key, "value": value})

                else:  # REFERENCES
                    if key.startswith("!S"):
                        # !S marks the beggining of a new reference block
                        current_reference_block = []
                        references.append(current_reference_block)
                        key = key[1:]

                    if not self.is_valid_source_id(key):
                        raise ParserException(f"Invalid source {key}")

                    current_reference_block.append({"property": "P" + key[1:], "value": value})
                    has_references = True

                index += 2

            if has_references:
                data["references"] = references

            if qualifiers:
                data["qualifiers"] = qualifiers

        return data

    def parse_comment(self, raw_command):
        comment = None
        m = re.search(r"^(.*?)\s*\/\*\s*(.*?)\s*\*\/\s*$", raw_command)
        if m:  # Extract comment as summary
            comment = m.group(2)
            raw_command = m.group(1)
        return raw_command, comment

    def parse_command(self, raw_command):
        raw_command, comment = self.parse_comment(raw_command)
        elements = raw_command.split("\t")
        if len(elements) == 0:
            raise ParserException("Empty command statement")

        first_command = elements[0].upper().strip()

        if first_command == "CREATE":
            data = self.parse_create(elements)
        elif first_command == "CREATE_PROPERTY":
            data = self.parse_create_property(elements)
        elif first_command == "MERGE":
            data = self.parse_merge(elements)
        elif first_command == "-STATEMENT":
            data = self.parse_statement_by_id(elements)
        else:
            data = self.parse_statement(elements, first_command)

        if comment:
            data["summary"] = comment

        return data

    def parse(self, batch_name, batch_owner, raw_commands):
        batch = Batch(name=batch_name, user=batch_owner)
        batch_commands = raw_commands.replace("||", "\n").replace("|", "\t")

        for index, raw_command in enumerate(batch_commands.split("\n")):
            bc = BatchCommand(
                batch=batch,
                index=index,
                raw=raw_command,
                json={},
                action=BatchCommand.ACTION_CREATE,
                status=BatchCommand.STATUS_INITIAL,
            )
            try:
                command = self.parse_command(raw_command)
                if command["action"] == "add":
                    bc.action = BatchCommand.ACTION_ADD
                    if command["what"] == "sitelink":
                        bc.operation = bc.Operation.SET_SITELINK
                elif command["action"] == "remove":
                    bc.action = BatchCommand.ACTION_REMOVE
                    what = command.get("what")
                    if what == "statement":
                        if "id" in command:
                            bc.operation = bc.Operation.REMOVE_STATEMENT_BY_ID
                        else:
                            bc.operation = bc.Operation.REMOVE_STATEMENT_BY_VALUE
                    elif what == "sitelink":
                        bc.operation = bc.Operation.REMOVE_SITELINK
                elif command["action"] == "create":
                    bc.action = BatchCommand.ACTION_CREATE
                    if command["type"] == "item":
                        bc.operation = bc.Operation.CREATE_ITEM
                    elif command["type"] == "property":
                        bc.operation = bc.Operation.CREATE_PROPERTY
                else:
                    bc.action = BatchCommand.ACTION_MERGE
                bc.user_summary = command.pop("summary", None)
                bc.json = command
            except ParserException as e:
                bc.status = BatchCommand.STATUS_ERROR
                bc.message = e.message

            batch.add_preview_command(bc)

        return batch
