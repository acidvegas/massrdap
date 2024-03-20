#!/usr/bin/env python
# RDAPr - developed by acidvegas (https://git.acid.vegas/massrdap)

import json
import urllib.request
import socket
import re

whois_rdap = {}

def whois_query(tld: str):
    '''
    Queries the IANA WHOIS server for TLD information.
    
    :param tld: The top-level domain to query.
    '''

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(('whois.iana.org', 43))
        sock.sendall((f'{tld}\r\n').encode())
        response = b''
        while True:
            data = sock.recv(4096)
            if not data:
                break
            response += data
            
    return response.decode(errors='replace')


def get_rdap():
    '''Fetches RDAP servers from IANA's RDAP Bootstrap file.'''

    with urllib.request.urlopen('https://data.iana.org/rdap/dns.json') as response:
        data = json.loads(response.read().decode('utf-8'))

        for entry in data['services']:
            tlds     = entry[0]
            rdap_url = entry[1][0]

            for tld in tlds:
                whois_rdap[tld] = {'rdap': rdap_url}

                
def get_whois():
    '''Fetches WHOIS servers from IANA's TLD list.'''

    with urllib.request.urlopen('https://data.iana.org/TLD/tlds-alpha-by-domain.txt') as response:
        tlds = response.read().decode('utf-8').lower().split('\n')[1:-1]

        for tld in tlds:
            if tld not in whois_rdap:
                whois_rdap[tld] = {'rdap': None}

            whois_data = whois_query(tld)
            whois_server = None
            for line in whois_data.split('\n'):
                if 'whois:' in line:
                    parts = line.split()
                    if len(parts) > 1:
                        whois_server = parts[1]
                    break
            
            if whois_server:
                whois_rdap[tld]['whois'] = whois_server
                print(f'WHOIS server for {tld}: {whois_server}')
            else:
                whois_rdap[tld]['whois'] = None
                print(f'No WHOIS server for {tld}.')



if __name__ == '__main__':
    get_rdap()
    
    TOTAL = len(whois_rdap)           
    print(f'Found RDAP for {TOTAL:,} TLDs!')
    
    get_whois()
    print(f'RDAP is not available for {len(whois_rdap) - TOTAL:,} TLDs.')

    whois_rdap = {key: whois_rdap[key] for key in sorted(whois_rdap)}

    with open('rdaps.json', 'w') as file:
        json.dump(whois_rdap, file, indent=4)
