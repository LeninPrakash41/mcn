"""MCN playground server, split by feature.  server.py builds the Flask app."""

BLUEPRINT_MODULES = ['site', 'auth', 'community', 'secrets_api', 'git_api', 'workspace', 'execute', 'simulators', 'agent', 'build', 'api_docs', 'devserver', 'examples']
