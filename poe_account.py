import json


class Account:

    def __init__(self, account_name):
        self._account_name = account_name
        self._characters = list()

    @property
    def account_name(self):
        """The account_name property."""
        return self._account_name

    @account_name.setter
    def account_name(self, value):
        self._account_name = value

    @property
    def characters(self):
        """The characters property."""
        return self._characters

    @characters.setter
    def characters(self, value):
        self._characters = value

    @property
    def extracted(self):
        """The extracted property."""
        return self._extracted

    @extracted.setter
    def extracted(self, value):
        self._extracted = value

    def __unicode__(self):
        strdict = dict()
        for key, value in self.__dict__.items():
            if isinstance(value, dict):
                subdict = dict()
                for k_dict, v_dict in value.items():
                    subdict[k_dict] = json.loads(v_dict)
                strdict[key] = subdict
            elif isinstance(value, list):
                subdict = list()
                for v_dict in value:
                    subdict.append(json.loads(v_dict))
                strdict[key] = subdict
            else:
                strdict[key] = value.encode('utf-8')
        return json.dumps(strdict, ensure_ascii=False, encoding="utf-8")

    def __eq__(self, other):
        if self.account_name == other.account_name:
            return True
        else:
            return False
