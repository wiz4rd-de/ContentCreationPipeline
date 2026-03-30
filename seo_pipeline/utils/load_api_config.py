"""Parse an api.env file and return DataForSEO credentials."""


def load_env(file_path: str) -> dict:
    """
    Parse an api.env file into { 'auth': str, 'base': str }.

    Skips empty lines and comment lines (starting with #).
    Splits each line on the first `=` only, so values may contain `=`.

    Args:
        file_path: absolute path to the env file

    Returns:
        A dict with keys 'auth' and 'base'

    Raises:
        ValueError: if DATAFORSEO_AUTH or DATAFORSEO_BASE are missing or empty
        FileNotFoundError: if the file does not exist
    """
    with open(file_path, encoding='utf-8') as f:
        content = f.read()

    env = {}
    for line in content.split('\n'):
        trimmed = line.strip()
        if trimmed == '' or trimmed.startswith('#'):
            continue
        eq_idx = trimmed.find('=')
        if eq_idx == -1:
            continue
        env[trimmed[:eq_idx]] = trimmed[eq_idx + 1:]

    auth = env.get('DATAFORSEO_AUTH')
    base = env.get('DATAFORSEO_BASE')

    if auth is None or auth == '':
        raise ValueError('DATAFORSEO_AUTH must be set in api.env')
    if base is None or base == '':
        raise ValueError('DATAFORSEO_BASE must be set in api.env')

    return {'auth': auth, 'base': base}
