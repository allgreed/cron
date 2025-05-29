import pytest
from datetime import date, timedelta
from cron import Weekly, Monthly, mk_Periodic, Reccuring

def test_weekly():
    assert Weekly(next_date=date(1990, 10, 1)).following_execution() == date(1990, 10, 8)


@pytest.mark.parametrize("next_date,result", [
    (date(1990, 4, 1), date(1990, 5, 1)),
    (date(1990, 2, 1), date(1990, 3, 1)),
    (date(1990, 12, 1), date(1991, 1, 1)),
])
def test_monthly(next_date, result):
    assert Monthly(next_date).following_execution() == result


def test_custom_class():
    class Custom(mk_Periodic(timedelta(days=45))):
        pass

    assert Custom(date(2024, 12, 8)).following_execution(date(2024, 10, 24)) == date(2024,12,8)


def test_serialization():
    class Tost(Reccuring):
        pass

    t = Tost(next_date=date(1990, 4, 1))
    assert Reccuring.from_dict(t.to_dict()) == t
