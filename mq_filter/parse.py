import re

class ParseError(Exception):
    pass


airline_code_pattern = r'(?<airline_code>8C|GB|ABX|ATN)'

two_letter_airline_codes = [
    '8C',
    'GB',
]

three_letter_airline_codes = [
    'ABX',
    'ATN',
]

class FlightPlanParser:

    def __init__(self, aftn_address):
        # Anticipating need to change this constant for queue migration.
        self.aftn_address = aftn_address

    def detect(self, first_line):
        if first_line.endswith(self.aftn_address):
            return self

    def __call__(self, text):
        data = {}
        lines = [line.strip() for line in text.splitlines()]

        if not lines[0].endswith(self.aftn_address):
            raise ParseError(f'Unexpeced first line {lines[0]}')

        data['airline_code'] = lines[1][8:][:2]

        if not data['airline_code'] not in two_letter_airline_codes:
            raise ParseError(f'Invalid airline code in second line lines[1]')

        return data


flight_plan = FlightPlanParser('ATLXRXA')

def apis(text):
    data = {}
    lines = [line.strip() for line in text.splitlines()]

    line_two_parts = lines[1].split()
    data['airline_code'] = line_two_parts[0][-2:]

    if data['airline_code'] not in two_letter_airline_codes:
        raise ParseError(f'Invalid airline code {data["airline_code"]}')

    return data

def dlnk(text):
    # Format 6 (APIS Crew) Line one
    # DLNKN1427A   GB  3110 19DEC2025MIA  CVG  GB     TEXT   111TEXT UPLINK                          PART 1 OF 1
    data = {}
    lines = [line.strip() for line in text.splitlines()]

    line_one_parts = lines[0].split()

    if not line_one_parts[0].startswith('DLNK'):
        raise ParseError('Line one does not start with DLNK: {lines[0]}')

    data['airline_code'] = line_one_parts[1]
    return data

def simple(text):
    # Parse simple messages with the format type code on one or two lines.
    data = {}
    lines = [line.strip() for line in text.splitlines()]

    qu_text, qu_data = lines[0].split()

    if qu_text != 'QU':
        raise ParseError('First Line does not start with "QU"')

    data['qu'] = qu_data

    # Third line is message format type
    data['format_type'] = lines[2]

    airline_line = 3
    if data['format_type'] == 'COR':
        # Add second format type and adjust which line has the airline
        data['format_type'] += ' ' + lines[3]
        airline_line = lines[4]
    else:
        airline_line = lines[3]

    if airline_line[:3] in three_letter_airline_codes:
        data['airline_code'] = airline_line[:3]
    elif airline_line[:2] in two_letter_airline_codes:
        data['airline_code'] = airline_line[:2]
    else:
        raise ParseError(f'Airline code not found: {lines[airline_line]}')

    return data

def detect(text):
    lines = [line.strip() for line in text.splitlines()]

    qu_parts = lines[0].split()
    if len(qu_parts) == 2:
        qu_text, qu_data = qu_parts
        if qu_text != 'QU':
            raise ParseError('First Line does not start with "QU"')

        if lines[2] in ('MVA', 'MVT', 'COR', 'DIV'):
            return simple
        elif flight_plan.detect(lines[0]):
            return flight_plan
        elif lines[0].endswith('SJOIMXA') or lines[0].endswith('DCAUCCR'):
            return apis
    elif lines[0].startswith('DLNKYABCD'):
        return dlnk
    else:
        raise ParseError(f'Parser not detected {text}')
