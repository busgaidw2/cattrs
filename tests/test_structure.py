"""Test structuring of collections and primitives."""
from cattr._compat import (List, Tuple, Any, Set, MutableSet, FrozenSet,
                           Dict, Optional, Union)

from pytest import raises

from hypothesis import assume, given
from hypothesis.strategies import (booleans, integers, floats, text, one_of,
                                   sampled_from, lists, tuples, sets,
                                   frozensets, just, binary, choices, data)

from cattr import Converter
from cattr._compat import bytes, unicode

from . import (primitive_strategies, seqs_of_primitives, lists_of_primitives,
               dicts_of_primitives, enums_of_primitives)

ints_and_type = tuples(integers(), just(int))
floats_and_type = tuples(floats(allow_nan=False), just(float))
strs_and_type = tuples(text(), just(unicode))
bytes_and_type = tuples(binary(), just(bytes))

primitives_and_type = one_of(ints_and_type, floats_and_type, strs_and_type,
                             bytes_and_type)

mut_set_types = sampled_from([Set, MutableSet])
set_types = one_of(mut_set_types, just(FrozenSet))


def create_generic_type(generic_types, param_type):
    """Create a strategy for generating parameterized generic types."""
    return one_of(generic_types,
                  generic_types.map(lambda t: t[Any]),
                  generic_types.map(lambda t: t[param_type]))


mut_sets_of_primitives = primitive_strategies.flatmap(
    lambda e: tuples(sets(e[0]), create_generic_type(mut_set_types, e[1]))
)

frozen_sets_of_primitives = primitive_strategies.flatmap(
    lambda e: tuples(frozensets(e[0]), create_generic_type(just(FrozenSet),
                                                           e[1]))
)

sets_of_primitives = one_of(mut_sets_of_primitives, frozen_sets_of_primitives)


@given(primitives_and_type)
def test_structuring_primitives(converter, primitive_and_type):
    """Test just structuring a primitive value."""
    # type: (Converter, Any) -> None
    val, t = primitive_and_type
    assert converter.structure(val, t) == val
    assert converter.structure(val, Any) == val


@given(seqs_of_primitives)
def test_structuring_seqs(converter, seq_and_type):
    """Test structuring sequence generic types."""
    # type: (Converter, Any) -> None
    iterable, t = seq_and_type
    converted = converter.structure(iterable, t)
    for x, y in zip(iterable, converted):
        assert x == y


@given(sets_of_primitives, set_types)
def test_structuring_sets(converter, set_and_type, set_type):
    """Test structuring generic sets."""
    # type: (Converter, Any, Type) -> None
    set_, input_set_type = set_and_type

    if input_set_type.__args__:
        set_type = set_type[input_set_type.__args__[0]]

    converted = converter.structure(set_, set_type)
    assert converted == set_

    # Set[int] can't be used with isinstance any more.
    non_generic = (set_type.__origin__ if set_type.__origin__ is not None
                   else set_type)
    assert isinstance(converted, non_generic)

    converted = converter.structure(set_, Any)
    assert converted == set_
    assert isinstance(converted, type(set_))


@given(sets_of_primitives)
def test_stringifying_sets(converter, set_and_type):
    """Test structuring generic sets and converting the contents to str."""
    # type: (Converter, Any) -> None
    set_, input_set_type = set_and_type

    input_set_type.__args__ = (unicode,)
    converted = converter.structure(set_, input_set_type)
    assert len(converted) == len(set_)
    for e in set_:
        assert unicode(e) in converted


@given(lists(primitives_and_type, min_size=1))
def test_structuring_hetero_tuples(converter, list_of_vals_and_types):
    """Test structuring heterogenous tuples."""
    # type: (Converter, List[Any]) -> None
    types = tuple(e[1] for e in list_of_vals_and_types)
    vals = [e[0] for e in list_of_vals_and_types]
    t = Tuple[types]

    converted = converter.structure(vals, t)

    assert isinstance(converted, tuple)

    for x, y in zip(vals, converted):
        assert x == y

    for x, y in zip(types, converted):
        assert isinstance(y, x)


@given(lists(primitives_and_type))
def test_stringifying_tuples(converter, list_of_vals_and_types):
    """Stringify all elements of a heterogeneous tuple."""
    # type: (Converter, List[Any]) -> None
    vals = [e[0] for e in list_of_vals_and_types]
    t = Tuple[(unicode,) * len(list_of_vals_and_types)]

    converted = converter.structure(vals, t)

    assert isinstance(converted, tuple)

    for x, y in zip(vals, converted):
        assert unicode(x) == y

    for x in converted:
        assert isinstance(x, unicode)


@given(dicts_of_primitives)
def test_structuring_dicts(converter, dict_and_type):
    # type: (Converter, Any) -> None
    d, t = dict_and_type

    converted = converter.structure(d, t)

    assert converted == d
    assert converted is not d


@given(dicts_of_primitives, data())
def test_structuring_dicts_opts(converter, dict_and_type, data):
    """Structure dicts, but with optional primitives."""
    # type: (Converter, Any, Any) -> None
    d, t = dict_and_type
    assume(t.__args__)
    t.__args__ = (t.__args__[0], Optional[t.__args__[1]])
    d = {k: v if data.draw(booleans()) else None for k, v in d.items()}

    converted = converter.structure(d, t)

    assert converted == d
    assert converted is not d


@given(dicts_of_primitives)
def test_stringifying_dicts(converter, dict_and_type):
    # type: (Converter, Any) -> None
    d, t = dict_and_type

    converted = converter.structure(d, Dict[unicode, unicode])

    for k, v in d.items():
        assert converted[unicode(k)] == unicode(v)


@given(primitives_and_type)
def test_structuring_optional_primitives(converter, primitive_and_type):
    """Test structuring Optional primitive types."""
    # type: (Converter, Any) -> None
    val, type = primitive_and_type

    assert converter.structure(val, Optional[type]) == val
    assert converter.structure(None, Optional[type]) is None


@given(lists_of_primitives().filter(lambda lp: lp[1].__args__))
def test_structuring_lists_of_opt(converter, list_and_type):
    """Test structuring lists of Optional primitive types."""
    # type: (Converter, List[Any]) -> None
    l, t = list_and_type

    l.append(None)
    args = t.__args__

    if args and args[0] not in (Any, unicode, Optional):
        with raises(TypeError):
            converter.structure(l, t)

    optional_t = Optional[args[0]]
    t.__args__ = (optional_t, )

    converted = converter.structure(l, t)

    for x, y in zip(l, converted):
        assert x == y

    t.__args__ = args


@given(lists_of_primitives())
def test_stringifying_lists_of_opt(converter, list_and_type):
    """Test structuring Optional primitive types into strings."""
    # type: (Converter, List[Any]) -> None
    l, t = list_and_type

    l.append(None)

    converted = converter.structure(l, List[Optional[unicode]])

    for x, y in zip(l, converted):
        if x is None:
            assert x is y
        else:
            assert unicode(x) == y


@given(lists(integers()))
def test_structuring_primitive_union_hook(converter, ints):
    """Test registering a union loading hook."""
    # type: (Converter, List[int]) -> None

    def structure_hook(cl, val):
        """Even ints are passed through, odd are stringified."""
        return val if val % 2 == 0 else unicode(val)

    converter.register_structure_hook(Union[unicode, int], structure_hook)

    converted = converter.structure(ints, List[Union[unicode, int]])

    for x, y in zip(ints, converted):
        if x % 2 == 0:
            assert x == y
        else:
            assert unicode(x) == y


@given(choices(), enums_of_primitives())
def test_structuring_enums(converter, choice, enum):
    """Test structuring enums by their values."""
    # type: (Converter, Any, Any) -> None
    val = choice(list(enum))

    assert converter.structure(val.value, enum) == val


def test_structuring_unsupported(converter):
    """Loading unsupported classes should throw."""
    # type: (Converter) -> None
    with raises(ValueError):
        converter.structure(1, Converter)
    with raises(ValueError):
        converter.structure(1, Union[int, unicode])
