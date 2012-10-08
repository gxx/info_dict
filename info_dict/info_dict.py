# coding=utf-8
"""
This file contains the utilities that enable a class deriving from the
InfoDict class to have tagged functions automatic evaluate at
initialization time and become items within its base dictionary class.
"""
from itertools import chain
from django.utils.safestring import mark_safe
from helpers import ConcatableDict, FrozenMeta
import types

# The name of the cache attribute to use for info item cache storage.
INFO_ITEM_CACHE_ATTRIBUTE_NAME = '_info_item_cache'


class InfoStoreItemPredicateFailure(StandardError):
    """Exception is thrown when a predicate fails for an info store item."""
    pass


class InfoStoreItemIgnoreError(StandardError):
    """Exception is thrown to signal an info store item should be ignored."""
    pass


class ConcatOptions(object):
    """Concatable attribute options.
    A container for options relating to joining an InfoDict class on
    one of its attributes tagged concatable.
    """
    __slots__ = ['exclude', 'include']

    def __init__(self, exclude=(), include=()):
        """The initializer for ConcatOptions.
        :param exclude: A container including the keys to exclude from the
             attribute's dictionary.
        :param include: A container containing the keys to include from the
            attribute's dictionary.
        """
        self.exclude = exclude
        self.include = include


class InfoDictAttributeInfo(object):
    """InfoDict attribute information.
    An object that contains the options applied to a function indicated to be
    used as an InfoDict attribute. Also acts as a factory for creation of
    the instance deriving from InfoStoreObjectBase.
    """
    __slots__ = ['_func', '_key', '_cache', '_predicate', '_concat',
                 '_marksafe']

    def __init__(self, func, key, cache, predicate, concat, marksafe):
        """Initializes InfoDictAttributeInfo with the function options.
        :param func: The function to represent as an item.
        :param cache: Whether to cache the return value.
        :param predicate: A predicate to check before attempting to resolve
            this item. Will reject from InfoStore on failure.
        :param marksafe: Whether to mark the returned value as safe for
            template usage without escaping the output.
        """
        if key is None and not concat:
            raise ValueError('key must be specified for non-concat attributes')

        self._func = func
        self._key = key
        self._cache = cache
        self._predicate = predicate
        # If it's True, it's simple empty concat options.
        self._concat = ConcatOptions() if concat is True else concat
        self._marksafe = marksafe

    @property
    def func(self):
        """:return: the function this instance represents options for."""
        return self._func

    @property
    def key(self):
        """:return: the key representing this function."""
        return self._key

    @property
    def cache(self):
        """:return: a boolean indicate whether caching is enabled."""
        return self._cache

    @property
    def predicate(self):
        """:return: the predicate to be levied against our function"""
        return self._predicate

    @property
    def concat(self):
        """:return: the concat options for this instance."""
        return self._concat

    @property
    def marksafe(self):
        """:return: True if output is marksafe'd, False otherwise."""
        return self._marksafe

    def get_instance(self):
        """Factory for creating item instance.
        A factory-like method that will create the instance of the item
        that can evaluated the function this option represents.
        :return: An instance deriving from InfoStoreObjectBase.
        """
        if self.concat:
            if isinstance(self.concat, ConcatOptions):
                return ConcatInfoStoreItem(self.func)
            else:
                raise TypeError('concat must be bool or ConcatOption type, is:'
                                ' "%s" type' % self.concat.__class__.__name__)
        else:
            return InfoStoreItem(self.func)


class InfoStoreObjectBase(object):
    """Base for InfoStore attribute types.
    A base for InfoStoreItems containing pulled-up methods and attributes
    necessary for determining how to process the virtual dictionary item
    from the function tagged.
    """

    def __init__(self, func):
        """Initializer for InfoStoreObjectBase.
        :return: func: The function to represent as an item.
        """
        self._func = func

    @property
    def func(self):
        """:return: the function this instance is wrapping."""
        return self._func

    @property
    def cache(self):
        """
        Returns a boolean indicating whether caching is turned on.
        """
        return self.func.info_attribute_options.cache

    @property
    def predicate(self):
        """:return: the predicate function for this attribute."""
        return self.func.info_attribute_options.predicate

    @property
    def marksafe(self):
        """:return: True if output is marksafe'd, otherwise False."""
        return self.func.info_attribute_options.marksafe

    @property
    def key(self):
        """:return: the key that represents the name of this item."""
        return self.func.info_attribute_options.key

    @property
    def concat(self):
        """Must be overridden in deriving classes.
        Indicates whether this instance is meant to be joined with the main
        info store or simple added as an item.
        :return: True if concatable, False otherwise.
        """
        raise NotImplementedError()

    def _get_and_process_value(self, instance):
        value = self.processvalue(instance)
        if self.marksafe:
            value = mark_safe(value)

        return value

    def _get_or_create_instance_cache(self, instance):
        # Use getattribute and setattr from object as we do not want any
        # overridden mechanics on the instance in question to affect the
        # process for getting and creating the instance cache store.
        try:
            cache_store = object.__getattribute__(
                instance, INFO_ITEM_CACHE_ATTRIBUTE_NAME)
        except AttributeError:
            cache_store = {}
            object.__setattr__(instance, INFO_ITEM_CACHE_ATTRIBUTE_NAME,
                               cache_store)

        return cache_store

    def getvalue(self, instance):
        """Get the value of this attribute.
        Will retrieve and return the value of this item based on the context
        of the instance passed as an argument.
        :param instance: The instance to use as a context for this process.
        :return: An evaluated value of undetermined type.
        """
        if self.predicate and not self.predicate(self, instance):
            raise InfoStoreItemPredicateFailure

        if self.cache:
            cache_store = self._get_or_create_instance_cache(instance)
            try:
                return cache_store[self.func]
            except KeyError:
                pass

        value = self._get_and_process_value(instance)

        # Finally cache the value
        if self.cache:
            cache_store[self.func] = value

        return value

    def processvalue(self, instance):
        """Must be overridden in deriving classes.
        A function that processed the value of this item from the context
        of the isntance provided.
        :param instance: The instance to use as a context for this process.
        :return: A (not yet fully) evaluated value of undetermined type.
        """
        raise NotImplementedError()


class InfoStoreItem(InfoStoreObjectBase):
    @property
    def concat(self):
        """This instance is not meant for concatenation.
        Indicates whether this instance is meant to be joined with the main
        info store or simple added as an item.
        :return: False.
        """
        return False

    def processvalue(self, instance):
        """Attribute specific processing.
        A function that processed the value of this item from the context
        of the isntance provided.
        :param instance: The instance to use as a context for this process.
        :return: A (not yet fully) evaluated value of undetermined type.
        """
        return self.func(instance)


class ConcatInfoStoreItem(InfoStoreObjectBase):
    def __init__(self, func):
        """
        Initializer for ConcatInfoStoreItem.
        Keyword Arguments:
            func: The function to represent as an item.
        """
        # Force conversion to set if not already, as it is more efficient
        # for the purposes we are using it for (mostly 'in' operations), +
        # should be unique anyhow.
        self._include = set(func.info_attribute_options.concat.include)
        self._exclude = set(func.info_attribute_options.concat.exclude)
        super(ConcatInfoStoreItem, self).__init__(func)

    @property
    def concat(self):
        """This instance is meant for concatenation.
        Indicates whether this instance is meant to be joined with the main
        info store or simple added as an item.
        :return: True.
        """
        return True

    @property
    def key(self):
        """:return: the key that represents the name of this item."""
        return hash(self.func)

    def isexcluded(self, key):
        """:return: True if the key passed is excluded, False otherwise."""
        return key not in self._include and key in self._exclude

    def isincluded(self, key):
        """:return: True if the key passed is included, False otherwise."""
        return not self.isexcluded(key)

    def processvalue(self, instance):
        """Attribute specific processing.
        Evaluates the function this instance wraps and ensures that only the
        parts specified by the exclude and include options this class
        contains are returned.
        :param instance: The instance to use as a context for this process.
        :return: A (not yet fully) evaluated value of undetermined type.
        """
        items = self.func(instance)
        return dict((key, items[key]) for key in items if self.isincluded(key))


class InstanceInfoStore(object):
    """
    An instance-based representation of InfoStore items, which, when
    evaluated, will retrieve the registered items held internally with the
    context passed at initialization as the context.
    """
    __metaclass__ = FrozenMeta

    def __init__(self, instance, registered_items=None):
        """
        The initializer for the InstanceInfoStore object.
        Keyword Arguments:
            instance: The instance to apply as a context when evaluated.
            registered_items: The items registered to the instance.
        """
        self._instance = instance
        self._registered_items = registered_items or {}

    @property
    def instance(self):
        """:return: the instance that is used as a context for evaluation."""
        return self._instance

    @property
    def registered_items(self):
        """:return: the items to evaluate against the context."""
        return self._registered_items

    def evaluate(self):
        """Retrieves the dictionary representation of this instance.
        A cached property that returns the evaluation of this instance.
        Levies the context passed at initialization against the registered
        items of the context, which are passed at evaluation, also.
        :return: A dictionary representing this object.
        """
        item_dict = {}
        for item_key, item_object in self._registered_items.iteritems():
            try:
                item_value = item_object.getvalue(self.instance)
            except (InfoStoreItemPredicateFailure, InfoStoreItemIgnoreError):
                continue
            else:
                if item_object.concat:
                    self.validate_unique_keys(item_dict, item_value)
                    item_dict.update(item_value)
                else:
                    item_dict[item_key] = item_value

        return item_dict

    def validate_unique_keys(self, dict_a, dict_b):
        """Validates key uniqueness of two dictionaries.
        Validates the keys of the two dictionaries. Raising an exception if
        there are any overlapping keys.
        :param dict_a: A dictionary to validate against.
        :param dict_b: A dictionary to validate against.
        :raises: ValueError if validation fails.
        """
        intersection = set(dict_a) & set(dict_b)
        if intersection:
            raise ValueError('Duplicate keys: %s' ', '.join(intersection))


class InfoStore(object):
    """Creates and stores marked attributes."""

    def __init__(self):
        """Initializer for InfoStore class."""
        self._registered_items = {}

    def __get__(self, instance, owner):
        """Retrieves instance or class level info stores.
        A descriptor getter that will get or create the InstanceInfoStore
        associated with the instance if this is called from an instance,
        otherwise return this instance, which is applied at class-level.
        :param instance: The object instance, if any.
        :param owner: The object class type.
        :return: A class representing the class or instance level info store.
        :raises: RunTimeError if no instance or owner.
        """
        if instance is not None:
            try:
                return instance._instance_info_store
            except AttributeError:
                return self._get_or_create_instance_info_store(instance)
        elif owner is not None:
            return self
        else:
            raise RuntimeError()

    @property
    def registered_items(self):
        """:return: the currently registered items for this instance."""
        return self._registered_items

    def _get_or_create_instance_info_store(self, instance):
        infostore = InstanceInfoStore(instance, self._registered_items)
        instance._instance_info_store = infostore
        return infostore

    def register(self, func):
        """Register an item for this instance.
        :param func: The function to represent as an item.
        :raises: ValueError if function key is a not unique in register store.
        """
        info_item = func.info_attribute_options.get_instance()
        if info_item.key in self.registered_items:
            raise ValueError('Duplicate key for info item attribute: %s'
                             % info_item.key)
        else:
            self.registered_items[info_item.key] = info_item


class InfoDictMeta(FrozenMeta):
    """Class for auto-populating InfoDict subclasses.
    A metaclass for InfoDict which will automatically create and evaluate the
    items marked on the deriving class (and its bases) as attributes and
    register those items within the created info store.
    """

    def __new__(mcs, name, bases, dct):
        """Creates a new type.
        Will also register an InfoStore instance on it.
        :param mcs: The metaclass levied to create the new type.
        :param name: The name of the new type.
        :param bases: The bases this type derives from.
        :param dct: The class-level attribute dictionary.
        :return: A new type with an InfoStore instance attached.
        """
        dct['info_store'] = InfoStore()
        return super(FrozenMeta, mcs).__new__(mcs, name, bases, dct)

    def __init__(cls, name, bases, dct):
        """Initializes the new type created by this metaclass.
        Will also register the attributes from the new type and its bases.
        :param cls: The new, uninitialized type.
        :param bases: The bases of cls.
        :param dct: The instance-level attribute dictionary.
        """
        base_attributes = InfoDictMeta._get_class_attributes(*bases)
        for func in chain(base_attributes, dct.itervalues()):
            if (hasattr(func, 'info_attribute_options')
                and type(func) in (types.FunctionType,
                                   types.UnboundMethodType)):
                cls.info_store.register(func)

        super(InfoDictMeta, cls).__init__(name, bases, dct)

    @staticmethod
    def _get_class_attributes(*klasses):
        for klass in klasses:
            for key in dir(klass):
                yield getattr(klass, key)


class InfoDict(ConcatableDict):
    """Class that automatically adds marked attributes to its dictionary.
    Classes deriving from this class represent a dictionary that loads its
    keys and values from functions tagged as attributes that utilize
    a chain of command to evaluate the method to determine the items.
    """
    __metaclass__ = InfoDictMeta

    def __init__(self, *args, **kwargs):
        """Initializer for InfoDict.
        Will add evaluated instance items to this instance's dictionary
        base storage.
        """
        super(InfoDict, self).__init__(*args, **kwargs)
        self.update(self.info_store.evaluate())

    def __getattr__(self, item):
        """Retrieves items as if they were attributes.
        Get attributes that cannot be found by utilizing getitem (to allow
        dictionary keys to be resolved as if they were attributes.)
        :param item: The dictionary key to look up.
        :return: An object indexed by item.
        :raises: AttributeError if item not found.
        """
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)

    @staticmethod
    def attribute(key=None, cache=False, predicate=None, concat=None,
                  marksafe=False):
        """Register an attribute with the options provided as arguments.
        :param key: The key to represent this attribute. Necessary for items that
            do not yield more than one key (i.e. not a concat item).
        :param cache: Whether to cache the return value.
        :param predicate: A predicate to check before attempting to resolve this
            item. Will reject from InfoStore on failure.
        :param marksafe: Whether to mark the returned value as safe for template
            usage without escaping the output.
        :return: A function decorator.
        """
        # NOTE: recommend to use get_function_name in function name definition
        # and name the resulting dictionary variable something else if attribute
        # is being used in a template. This is due to the template resolution
        # in combination with using skip(). This will cause the dict
        # resolution to fail and an attempt to resolve the name as an attribute.
        # This does not occur if the resulting dictionary is combined with
        # another.
        def _attribute_decorator(func):
            func.info_attribute_options = InfoDictAttributeInfo(
                func, key, cache, predicate, concat, marksafe)
            return func

        return _attribute_decorator

    def skip(self):
        """Skips the attribute that is currently being processed."""
        raise InfoStoreItemIgnoreError()
