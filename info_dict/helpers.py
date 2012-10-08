# coding=utf-8
"""
This file contains various methods generic to or that help the
construction of the tracking library functionality.
"""


class FrozenMeta(type):
    """Metaclass for freezing the typed class after initializing."""

    def __new__(mcs, name, bases, dct):
        """Creates a new type.
        Adds the freezeable __setattr__ to the class type.
        :param mcs: The metaclass type.
        :param name: A string representing the class name.
        :param bases: Superclasses of the new class type.
        :param dct: The class attribute dictionary.
        :return: A new type.
        """
        dct['__setattr__'] = mcs.setattr
        return  super(FrozenMeta, mcs).__new__(mcs, name, bases, dct)

    def __init__(cls, name, bases, dct):
        """Initializes the new type.
        Sets the initial frozen value of the frozen setattr to False
        i.e. do not freeze the class setter.
        :param cls: The class type.
        :param name: A string representing the class name.
        :param bases: Superclasses of the new class type.
        :param dct: The class instance attribute dictionary.
        """
        cls._frozen = False
        super(FrozenMeta, cls).__init__(name, bases, dct)

    def __call__(cls, *args, **kwargs):
        """Call chain for type creation.
        Freezes the instance after it has been initialized.
        :param cls: The class type.
        :param args: Arguments passed to class initializer.
        :param kwargs: Keyword arguments passed to the class initializer.
        :return: A new instance of cls type.
        """
        instance = super(FrozenMeta, cls).__call__(*args, **kwargs)
        # Freeze after instance is set up
        instance._frozen = True
        return instance

    @staticmethod
    def setattr(self, key, value):
        """The setter for this class is frozen after initialization.
        :param key: Key to set
        :param value: Value to set.
        """
        if getattr(self, '_frozen', False):
            raise RuntimeError('%s is frozen.' % self.__class__.__name__)
        else:
            super(self.__class__, self).__setattr__(key, value)


class ConcatableDict(dict):
    """A dictionary subclass that provides arithmetic concatenation methods.
    Will allow the addition of two dictionaries together, should one of those
    dictionaries be a dict subclass of ConcatableDict type.
    Important: will give preference to the dictionary-like object on the
    right-hand side of the equation should keys overlaps.
    """
    @staticmethod
    def join_dicts(dicta, dictb):
        """Joins two dictionaries"""
        new_dict = ConcatableDict(dicta)
        new_dict.update(dictb)
        return new_dict

    def __add__(self, other):
        """Left-hand side addition overloader.
        Will add together this object with other, with keys from this object
        taking precedent.
        :param other: The other dictionary-like object to combine with.
        :return: A new DictConcatWrapper object with the combined dictionaries.
        """
        return ConcatableDict.join_dicts(self, other)

    def __radd__(self, other):
        """Right-hand side addition overloader.
        Will add together this object with other, with keys from other object
        taking precedent.
        :param other: The other dictionary-like object to combine with.
        :return: A new DictConcatWrapper object with the combined dictionaries.
        """
        return ConcatableDict.join_dicts(other, self)

    def copy(self):
        """Overrides the dict.copy method to return a ConcatableDict type.
        :return: ConcatableDict copy.
        """
        return ConcatableDict(self)
