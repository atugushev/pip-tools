from six.moves.urllib.request import pathname2url


def pathname_to_url(path):
    """
    Given a path to a file, returns an URL with 'file://' scheme
    """
    return 'file://' + pathname2url(path)
