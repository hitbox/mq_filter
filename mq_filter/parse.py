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
    'DIV': airline_codes_3letter_regex,
}

apis_regex = re.compile(r'\.ILNDD(?P<airline_code>GB|8C)')

flight_plan_regex = re.compile(r'^\(FPL-(?P<airline_code>ATN|ABX)')

two_letter_airline_codes = {'8C', 'GB'}

three_letter_airline_codes = {'ABX', 'ATN'}

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

    if not lines[0].startswith('QU'):
        raise ParseError('Non-DLNK message must start with QU')

    msg_format = lines[2]
    data.update({
        'format': msg_format,
    })
    if msg_format == 'COR' and lines[3] in message_types:
        # COR message format which includes the type on the next line. After
        # that the the lines are parsed similarly to Non-COR messages.
        # Update type from next line
        if lines[3] not in message_types:
            raise ParseError(
                f'COR message must have one of {message_types=} in line after'
                f' COR-line: {lines[3]=}')

        data['type'] = lines[3]
        # COR message is 2-letter airline code.
        if lines[4] not in two_letter_airline_codes:
            raise ParseError(
                f'COR message must have two-letter airline code'
                f' {lines[2:5]=}')
        data['airline_code'] = lines[4]
    elif msg_format in message_types:
        regex = regex_for_format[msg_format]
        # Non-COR message format. Using looked-up regex for format to enforce
        # expected airline code length.
        match = regex.match(lines[3])
        if match:
            data.update(match.groupdict())
        else:
            raise ParseError(
                'Unable to find airline code for Non-COR format:'
                f'{lines[2:4]=} {regex=}')
    else:
        # Try APIS before flight plan, on second line
        match = apis_regex.match(lines[1])
        if match:
            data.update(match.groupdict())
        else:
            # Finally, search for flight plan type line-by-line because the ^FF
            # line can wrap with newlines.
            for line in lines:
                match = flight_plan_regex.match(line)
                if match:
                    data.update(match.groupdict())
                    break
            else:
                raise ParseError(
                    f'Unable to find flight plan with {flight_plan_regex=}')
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
