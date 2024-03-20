#!/usr/bin/env python
# MassRDAP - developed by acidvegas (https://git.acid.vegas/massrdap)

import argparse
import asyncio
import logging
import json
import re

try:
    import aiofiles
except ImportError:
    raise ImportError('missing required aiofiles library (pip install aiofiles)')

try:
    import aiohttp
except ImportError:
    raise ImportError('missing required aiohttp library (pip install aiohttp)')

# Color codes
BLUE   = '\033[1;34m'
CYAN   = '\033[1;36m'
GREEN  = '\033[1;32m'
GREY   = '\033[1;90m'
PINK   = '\033[1;95m'
PURPLE = '\033[0;35m'
RED    = '\033[1;31m'
YELLOW = '\033[1;33m'
RESET  = '\033[0m'

# Setup basic logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Global variable to store RDAP servers
RDAP_SERVERS = {}

async def fetch_rdap_servers():
    '''Fetches RDAP servers from IANA's RDAP Bootstrap file.'''

    async with aiohttp.ClientSession() as session:
        async with session.get('https://data.iana.org/rdap/dns.json') as response:
            data = await response.json()
            for entry in data['services']:
                tlds = entry[0]
                rdap_url = entry[1][0]
                for tld in tlds:
                    RDAP_SERVERS[tld] = rdap_url


def get_tld(domain: str):
    '''Extracts the top-level domain from a domain name.'''
    parts = domain.split('.')
    return '.'.join(parts[1:]) if len(parts) > 1 else parts[0]


async def lookup_domain(domain: str, proxy_url: str, semaphore: asyncio.Semaphore, success_file, failure_file):
    '''
    Looks up a domain using the RDAP protocol.
    
    :param domain: The domain to look up.
    :param proxy_url: The proxy URL to use for the request.
    :param semaphore: The semaphore to use for concurrency limiting.
    '''

    async with semaphore:
        tld = get_tld(domain)

        rdap_url = RDAP_SERVERS.get(tld)

        if not rdap_url:
            return

        query_url = f'{rdap_url}domain/{domain}'

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(query_url, proxy=proxy_url if proxy_url else None) as response:

                    if response.status == 200:
                        data = await response.json()
                        await success_file.write(json.dumps(data) + '\n')
                        print(f'{GREEN}SUCCESS {GREY}| {BLUE}{response.status} {GREY}| {PURPLE}{rdap_url.ljust(50)} {GREY}| {CYAN}{domain}{GREEN}')

                    else:
                        await failure_file.write(domain + '\n')
                        print(f'{RED}FAILED  {GREY}| {YELLOW}{response.status} {GREY}| {PURPLE}{rdap_url.ljust(50)} {GREY}| {CYAN}{domain}{RESET}')

        except Exception as e:
            print(f'{RED}FAILED  {GREY}| --- | {PURPLE}{rdap_url.ljust(50)} {GREY}| {CYAN}{domain} {RED}| {e}{RESET}')


async def process_domains(args: argparse.Namespace):
    '''
    Processes a list of domains, performing RDAP lookups for each one.
    
    :param args: The parsed command-line arguments.
    '''
    
    await fetch_rdap_servers() # Populate RDAP_SERVERS with TLDs and their RDAP servers

    if not RDAP_SERVERS:
        logging.error('No RDAP servers found.')
        return
    
    semaphore = asyncio.Semaphore(args.concurrency)

    async with aiofiles.open(args.output, 'w') as success_file, aiofiles.open(args.failed, 'w') as failure_file:
        async with aiofiles.open(args.input_file) as file:
            async for domain in file:
                domain = domain.strip()
                if domain:
                    await semaphore.acquire()
                    task = asyncio.create_task(lookup_domain(domain, args.proxy, semaphore, success_file, failure_file))
                    task.add_done_callback(lambda t: semaphore.release())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Perform RDAP lookups for a list of domains.')
    parser.add_argument('-i', '--input_file', required=True, help='File containing list of domains (one per line).')
    parser.add_argument('-p', '--proxy', help='Proxy in user:pass@host:port format. If not supplied, none is used.')
    parser.add_argument('-c', '--concurrency', type=int, default=25, help='Number of concurrent requests to make. (default: 25)')
    parser.add_argument('-o', '--output', default='output.json', help='Output file to write successful RDAP data to. (default: output.json)')
    parser.add_argument('-f', '--failed', default='failed.txt', help='Output file to write failed domains to. (optional)')
    args = parser.parse_args()

    if not args.input_file:
        raise ValueError('File path is required.')

    if args.concurrency < 1:
        raise ValueError('Concurrency must be at least 1.')
        
    if args.proxy:
        if not re.match(r'^https?:\/\/[^:]+:[^@]+@[^:]+:\d+$', args.proxy):
            raise ValueError('Invalid proxy format. Must be in user:pass@host:port format.')
        
    if not args.output:
        raise ValueError('Output file path is required.')
    
    if not args.failed:
        print(f'{YELLOW}Failed domains will not be saved.{RESET}')
        
    asyncio.run(process_domains(args))