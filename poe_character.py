import json


class Character:

    def __init__(self, character_name, league):
        self._name = character_name
        self._league = league

    @property
    def name(self):
        """The _name property."""
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def league(self):
        """The league property."""
        return self._league

    @league.setter
    def league(self, value):
        self._league = value

    def __unicode__(self):
        return json.dumps(self.__dict__, ensure_ascii=False, encoding="utf-8")

    def __eq__(self, other):
        if self.name == other.name and self.league == other.league:
            return True
        else:
            return False
