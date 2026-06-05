# capture language specific

### python

capturing the request, aiohttp, and urllibs package

### Node

capturing fetch, and others

non-streaming:

- going to use python/ts/js to capture the HTTP packages core thing
- request and response will be directly provided to c without filtration

streaming:

- going to use same like non-streaming mode
- request will be sent but response will be filtered only last chunk will passed to c.
