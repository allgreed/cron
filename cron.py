import json
import subprocess
from typing import Optional, Sequence, Union
from datetime import datetime, timedelta, date
from dataclasses import dataclass
from dateutil.relativedelta import relativedelta
from contextlib import contextmanager

import typer
from tasklib import TaskWarrior, Task as _Task


def _main(db_file_name="crondb.json"):
    today = datetime.now().date()
    tw = TaskWarrior()

    crondb = CronDB(db_file_name).load()
    state = restore_reccurings(crondb)

    # TODO: check journal if empty
        # else: handle journal
    # TODO: is this the right place to handle journal?

    for reccuring in state:
        if reccuring.is_due(today):
            if reccuring.is_overdue(today):
                print(f"warning: {reccuring.name}: overdue!")

            while (new_next_date := reccuring.following_execution()) < today:
                reccuring.next_date = new_next_date # following_execution usues self.next_date, this is a hack

                # essentially skip the missing occurance
                print(f"warning: {reccuring.name}: was supposed to happen on {new_next_date} - in the past, skipping")

            # TODO: do a dry-runable version as well
            with crondb.journaled_write(reccuring.name, new_next_date):
                # TODO: how to make the runners indempotent? o.0 -> for the future
                # I could enforce indempotency by running it between 1 and 3 times at random
                reccuring.schedule(tw)
                reccuring.next_date = new_next_date
                print(f"{reccuring.name}: Next execution is {new_next_date}")


        if reccuring.interval_rollover_enable:
            assert hasattr(reccuring, "task"), "interval_rollover-enabled Reccurings has an associated Task"
            _tw_task = sorted(
                    tw.tasks.filter("+COMPLETED", description=reccuring.task["description"]),
                    key=lambda t: t["end"], reverse=True)

            try:
                tw_task = _tw_task[0]
            except IndexError:  # task not found
                # I fucking hate this non-obvious control flow hack
                # TODO: make it nicer
                continue

            last_end = tw_task["end"].date()
            next_date_from_last_completion = reccuring.following_execution(last_end)

            if reccuring.next_date < next_date_from_last_completion:
                crondb.write(reccuring.name, next_date_from_last_completion)
                print(f"{reccuring.name}: perofrmed interaval rollover - next execution of  is {next_date_from_last_completion} instead of {reccuring.next_date}")


class Task(_Task):
    def __init__(self, description, *,
                 urgent: Optional[bool] = None,
                 important: Optional[bool] = None,
                 home: bool = False,
                 next: bool = False,
                 **kwargs):
        def set_bool_UDA_if_set(prop, value):
            if value is not None:
                kwargs[prop] = "T" if value else "F"

        set_bool_UDA_if_set("urgent", urgent)
        set_bool_UDA_if_set("important", important)

        super().__init__(None, description=description, **kwargs)

        tags = self["tags"]
        assert isinstance(tags, set), "tags are initialized on the Task instance"
        if home:
            tags.add("home")
        if next:
            tags.add("home")


# TODO: make it a proper interface
@dataclass
class Reccuring:
    next_date: date

    interval_rollover_enable = False
    autountil = True
    run_after = set()
    # TODO: how about I just drop the dataclass?
    # because the annotations would be pretty neat
    # TODO: also: notion of exclusivness!
    # task: Optional[Task] = None
    # script: Optional[str] = None

    _templates = set()

    def following_execution(self) -> date:
        raw_date = input(f"{self.__class__.__qualname__} - następna data? ")
        return parse_date(raw_date)

    def is_due(self, today):
        return self.next_date <= today

    def is_overdue(self, today):
        return self.next_date < today

    @classmethod
    @property
    def name(cls):
        return cls.__qualname__

    def schedule(self, tw: TaskWarrior) -> None:
        # TODO: unhack? xD so that the requirement is explicit
        # that it must either have "script" or overwrite this method
        if hasattr(self, "script"):
            return self.run_script(self.script)
        elif hasattr(self, "task"):
            return self.run_task(tw, self.task)
        elif hasattr(self, "shell"):
            subprocess.run(self.shell, shell=True, check=True)
            return
        else:
            assert 0, "unreachable"

    @classmethod
    def get_subclasses(cls):
        for subclass in cls.__subclasses__():
            yield from subclass.get_subclasses()
            if subclass not in cls._templates:
                yield subclass

    def run_task(self, tw: TaskWarrior, task: Task) -> None:
        task.backend = tw

        if self.autountil:
            # TODO: pass now as dependency?
            task["until"] = datetime.now().date() + self.period

        task["tags"].add("cron")

        task.save()

    def run_script(self, script: str) -> None:
        self.ask_to(f"Please run: {script}") 

    def ask_to(self, text: str) -> None:
        print(text)
        done = False
        while not done:
            done = self.confirm("Done?")

    def confirm(self, text: str) -> bool:
        return typer.confirm(text)


def mk_Periodic(interval: Union[timedelta, relativedelta]):
    class Periodic(Reccuring):
        period = interval

        def following_execution(self, _interval_start: Optional[date] = None):
            interval_start = _interval_start or self.next_date
            return interval_start + interval

    Reccuring._templates.add(Periodic)
    return Periodic

Weekly = mk_Periodic(timedelta(days=7))
Biweekly = mk_Periodic(timedelta(days=14))
Monthly = mk_Periodic(relativedelta(months=+1))
Bimonthly = mk_Periodic(relativedelta(months=+2))
Quarterly = mk_Periodic(relativedelta(months=+3))
Semiyearly = mk_Periodic(relativedelta(months=+6))
Yearly = mk_Periodic(relativedelta(years=+1))


def parse_date(raw_date: str, now_fn=lambda: datetime.now()) -> date:
    now = now_fn()

    # TODO: can I use taskwarrior parsing here? :D
    try:
        return datetime.strptime(raw_date, "%d.%m").date().replace(year=now.year)
        # TODO: support year wrapping if it's for example March and the date is 2.02
        # then it's clearly Feburary next year
    except ValueError:
        return datetime.strptime(raw_date, "%d.%m.%Y").date()


class CronDB(dict):
    # TODO: make it resiliant
    # https://danluu.com/deconstruct-files/
    # TODO: do I check for ZFS?

    def __init__(self, db_file_name: str):
        self.db_file_name = db_file_name
        
    def load(self) -> "CronDB": 
        # TODO: handle file not existing
        # TODO: handle trailing comma
        with open(self.db_file_name, mode="r") as db_file:
            self.update(json.load(db_file))
        return self

    def write(self, recurring_name: str, new_next_date: date) -> None:
        self[recurring_name] = new_next_date.strftime("%Y-%m-%d")
        with open(self.db_file_name, mode="w", encoding ='utf8') as db_file:
            json.dump(self, db_file, indent=4)
            db_file.write("\n") # ensure no diff at the end of a file when editing by hand
            db_file.flush()

    @contextmanager
    def journaled_write(self, reccuring_name, new_next_date):
        # TODO: journal intent
        # pickle sounds reasonable?
        try:
            yield
            self.write(reccuring_name, new_next_date)
            # TODO: unjournal intent
        finally:
            pass


def restore_reccurings(crondb: CronDB) -> Sequence[Reccuring]:
    classMapping = {cls.name : cls for cls in leaf_subclasses(Reccuring)}

    for identifier in classMapping:
        if identifier not in crondb:
            crondb.write(identifier, parse_date(input(f"Next date for {identifier}? ")))
    assert all(i in crondb for i in classMapping), "for every existing class there is an entry in crondb"
    # TODO: make this a validation

    if additional := set(crondb).difference(set(classMapping)):
        print(f"warrning: {crondb.db_file_name} has additional entries {additional} that do not have a matching Reccuring definition")

    def _reconstruct_task(args):
        task_name, raw_next_date = args
        next_date = datetime.strptime(raw_next_date, "%Y-%m-%d").date()
        return classMapping[task_name](next_date)
    return  sorted(map(_reconstruct_task, crondb.items()), key=lambda t: t.run_after)
    # !!! THIS IS WRONG, HOWVER IT's ALSO DONE !!!
    # TODO: implement actual dependency chain resolution, not just this


def leaf_subclasses(cls):
    return filter(lambda c: not c.__subclasses__(), cls.get_subclasses())


def main():
    typer.run(_main)


if __name__ == "__main__":
    print("you've likedly meant 'python mycron.py'")
    exit(1)
