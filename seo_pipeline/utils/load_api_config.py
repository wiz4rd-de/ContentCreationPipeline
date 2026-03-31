"""Parse an api.env file and return DataForSEO credentials."""

from pathlib import Path

from dotenv import dotenv_values


def load_env(file_path: str) -> dict:
    """
    Parse an api.env file into { 'auth': str, 'base': str }.

    Args:
        file_path: absolute path to the env file

    Returns:
        A dict with keys 'auth' and 'base'

    Raises:
        ValueError: if DATAFORSEO_AUTH or DATAFORSEO_BASE are missing or empty
        FileNotFoundError: if the file does not exist
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"No such file or directory: '{file_path}'")

    env = dotenv_values(file_path)

    auth = env.get('DATAFORSEO_AUTH')
    base = env.get('DATAFORSEO_BASE')

    if not auth:
        raise ValueError('DATAFORSEO_AUTH must be set in api.env')
    if not base:
        raise ValueError('DATAFORSEO_BASE must be set in api.env')

    return {'auth': auth, 'base': base}
