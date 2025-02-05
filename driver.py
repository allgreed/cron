import datetime
from cron import mk_Periodic, Task
from tasklib import TaskWarrior


class Tost(mk_Periodic(timedelta(days=45))):
    task = T("tost +quick", urgent=True, important=False, home=True, next=True)

tw = TaskWarrior()
t = TestTost(datetime.date(2024, 11, 3))
t.run_task(tw, t.task)
