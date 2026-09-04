"""
mq_filter scheduled tasks management script.
"""
import argparse
import configparser
import csv
import io
import os
import subprocess

from pprint import pprint

action2command = {
    'status': '/Query',
    'query': '/Query',
    'stop': '/End',
    'start': '/Run',
    'restart': ['/End', '/Run'],
}

machinable_actions = {'status', 'query'}

def schtasks(taskname, command, machine=False):
    cmd = ['schtasks.exe', command, '/Tn', taskname]
    if machine:
        cmd.extend(['/FO', 'CSV'])
    return subprocess.run(cmd, check=True, capture_output=True, text=True)

def main(argv=None):
    parser = argparse.ArgumentParser(
        description = 'Manage the mq filter scheduled tasks.',
    )
    parser.add_argument('--config', nargs='+', default='instance/schtasks.ini')
    choices = list(action2command.keys())
    parser.add_argument('action', nargs='?', default=choices[0], choices=choices)
    parser.add_argument('--machine', action='store_true')
    args = parser.parse_args(argv)

    for config_path in args.config:
        if not os.path.exists(args.config):
            parser.error(f'Config does not exist: {args.config}')

    if args.machine and args.action not in machinable_actions:
        parser.error(f'Machine output is only available for actions={machinable_actions}.')

    cp = configparser.ConfigParser()
    cp.read(args.config)

    appname = os.path.basename(__file__)
    appcp = cp[appname]

    tasknames = appcp['tasks'].splitlines()

    commands = action2command[args.action]
    if not isinstance(commands, list):
        commands = [commands]

    # Only used for collecting machine readable outputs.
    rows = []
    for command in commands:
        if args.action not in machinable_actions:
            print(f'{command}')

        for taskname in tasknames:
            completed = schtasks(taskname, command, machine=args.machine)
            if args.machine:
                reader = csv.DictReader(io.StringIO(completed.stdout))
                rows.extend(reader)
            else:
                print(completed.stdout)

    if args.machine and rows:
        # Print a nicely formatted table of collected CSV data.
        # Build conventional table of rows with fieldnames as first row
        table = [tuple(rows[0].keys())]
        for row in rows:
            table.append(tuple(row.values()))
        # Build our justification values.
        columns = list(zip(*table))
        column_lengths = [max(map(len, column_values)) for column_values in columns]
        separator = ' | '
        formatted_table = [separator.join(string.ljust(width) for width, string in zip(column_lengths, row)) for row in table]
        print('\n'.join(formatted_table))

if __name__ == '__main__':
    main()
