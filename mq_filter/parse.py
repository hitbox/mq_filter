import re
import string

class ParseError(Exception):
    pass


airline_codes_regex = re.compile(r'^(?P<airline_code>ATN|ABX|8C|GB)')
airline_codes_3letter_regex = re.compile(r'^(?P<airline_code>ATN|ABX)')

message_types = [
    'MVA',
    'MVT',
    'DIV',
]

regex_for_format = {
    'MVT': airline_codes_regex,
    'MVA': airline_codes_regex,
    'DIV': airline_codes_regex,
}

apis_regex = re.compile(r'(?P<prefix>\.ILNDD)(?P<airline_code>GB|8C)')

### Second Switchover Attempt ###
# 2026-03-04 Monday
# Originally this was expected to be (FPL- and then the airline code.
# Testing switch-over this morning showed other values CNL, DLA, CHG.
# The FF in that line, is a priority (mentioned by someone on the call).
flight_plan_regex = re.compile(r'^\((?P<aftn_type>CHG|CNL|DLA|FPL)-(?P<airline_code>ATN|ABX)')

fallback_regex = re.compile(r'.*K(?P<airline_code>ATN|ABX)[A-Z]$')

two_letter_airline_codes = {'8C', 'GB'}

three_letter_airline_codes = {'ABX', 'ATN'}

airline_codes = two_letter_airline_codes.union(three_letter_airline_codes)

def parse_content_for_airline(content):
    # Filter for only printable characters and split lines without keeping the
    # newline characters.
    lines = printable_splitlines(content)

    data = {}
    if lines[0].startswith('DLNK'):
        # DLNK indicated on first line. There should be whitespace between this
        # starting text and the two- or three-letter airline code.
        line_one_parts = lines[0].split()
        first_part_line_one = line_one_parts[1]
        if first_part_line_one not in two_letter_airline_codes:
            raise ParseError(
                f'DLNK detected but {first_part_line_one=} not in {two_letter_airline_codes=}'
            )
        data.update({
            'airline_code': first_part_line_one,
            'type': 'DLNK',
            'format': 'DLNK',
        })
        return data

    if not lines[0].startswith('QU'):
        raise ParseError(f'Non-DLNK message must start with "QU" {lines[0]=}')

    msg_format = lines[2]
    if msg_format == 'COR' and lines[3] in message_types:
        # COR message format which includes the type on the next line. After
        # that the the lines are parsed similarly to Non-COR messages.
        # Update type from next line
        if lines[3] not in message_types:
            raise ParseError(
                f'COR message must have one of {message_types=} in line after'
                f' COR-line: {lines[3]=}')

        data['type'] = lines[3]
        # COR message is 2- or 3-letter airline code.
        match = airline_codes_regex.match(lines[4])
        if not match:
            raise ParseError(
                f'COR message {lines[4]=} airline code not matched {airline_codes_regex=}')
        data.update(match.groupdict())
    elif msg_format in message_types:
        regex = regex_for_format[msg_format]
        # Non-COR message format. Using looked-up regex for format to enforce
        # expected airline codes.
        match = regex.match(lines[3])
        if match:
            data.update(match.groupdict())
            data.update({'regex': regex})
        else:
            raise ParseError(
                'Unable to find airline code for Non-COR format:'
                f'{lines[3]=} {regex=}')
    else:
        # Try APIS before flight plan, on second line
        match = apis_regex.match(lines[1])
        if match:
            data.update(match.groupdict())
            data.update({'found': 'APIS', 'line': 2})
        else:
            # Finally, search for flight plan type line-by-line because the ^FF
            # line can wrap with newlines.
            for ln, line in enumerate(lines, start=1):
                match = flight_plan_regex.match(line)
                if match:
                    data.update(match.groupdict())
                    data.update({'found': 'AFTN flight plan', 'line': ln})
                    break
            else:
                # Fallback search
                for ln, line in enumerate(lines, start=1):
                    match = fallback_regex.match(line)
                    if match:
                        data.update(match.groupdict())
                        data.update({'found': 'fallback search', 'line': ln})
                        break
                else:
                    raise ParseError(
                        f'Unable to find line with either {flight_plan_regex=} or {fallback_regex=} for {content=}')
    return data

def printable_splitlines(text):
    """
    Keeping only printable characters, split into a list of lines.
    """
    # Keep whitespace for later splitting of lines.
    lines = [''.join([char for char in line if char in string.printable]) for line in text.splitlines() ]
    return lines

def extract_payload_from_mq(message):
    """
    Extract the application payload from an IBM MQ message.

    Parses RFH2 folders as XML and returns only the application payload.
    """
    # If no RFH2, decode directly
    if not message.startswith(b"RFH "):
        return message.decode("utf-8")

    # RFH2 header length (bytes 8–11, big endian)
    header_len = int.from_bytes(message[8:12])
    payload = message[header_len:]

    # Remaining bytes (decoded) == payload
    return payload.decode()
