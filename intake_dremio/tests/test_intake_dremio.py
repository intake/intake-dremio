import intake

from intake_dremio import DremioSource

# pytest imports this package last, so plugin is not auto-added
intake.registry['dremio'] = DremioSource

def test_constructor():
    source = DremioSource('user:password@localhost:32010', 'SELECT * FROM table')
    assert source._user == 'user'
    assert source._password == 'password'
    assert source._hostname == 'localhost:32010'
