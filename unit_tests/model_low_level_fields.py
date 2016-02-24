# Copyright (C) 2016 Cisco Systems, Inc. and/or its affiliates. All rights reserved.
#
# This file is part of Kitty.
#
# Kitty is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# Kitty is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Kitty.  If not, see <http://www.gnu.org/licenses/>.

'''
Tests for low level fields:
'''
from common import metaTest, BaseTestCase
from bitstring import Bits
import hashlib
import types
from struct import unpack
from kitty.model import String, Delimiter, RandomBits, RandomBytes, Dynamic, Static, Group
from kitty.model import BitField, UInt8, UInt16, UInt32, UInt64, SInt8, SInt16, SInt32, SInt64
from kitty.model import Clone, Size, SizeInBytes, Md5, Sha1, Sha224, Sha256, Sha384, Sha512
from kitty.model import ElementCount, IndexOf
from kitty.model import Container
from kitty.core import KittyException


class CalculatedTestCase(BaseTestCase):
    __meta__ = True

    def setUp(self, cls=None):
        super(CalculatedTestCase, self).setUp(cls)
        self.depends_on_name = 'depends_on'
        self.depends_on_value = 'the_value'

    def calculate(self, field):
        '''
        :param field: field to base calculation on
        :return: calculated value
        '''
        raise NotImplemented

    def get_default_field(self, fuzzable=False):
        return self.cls(self.depends_on_name, fuzzable=fuzzable)

    def get_original_field(self):
        return String(self.depends_on_value, name=self.depends_on_name)

    @metaTest
    def test_calculated_after_field(self):
        original_field = self.get_original_field()
        calculated_field = self.get_default_field()
        container = Container([original_field, calculated_field])
        expected = self.calculate(original_field)
        actual = calculated_field.render()
        self.assertEqual(expected, actual)
        while container.mutate():
            expected = self.calculate(original_field)
            actual = calculated_field.render()
            self.assertEqual(expected, actual)

    @metaTest
    def test_calculated_before_field(self):
        original_field = self.get_original_field()
        calculated_field = self.get_default_field()
        container = Container([calculated_field, original_field])
        expected = self.calculate(original_field)
        actual = calculated_field.render()
        self.assertEqual(expected, actual)
        while container.mutate():
            expected = self.calculate(original_field)
            actual = calculated_field.render()
            self.assertEqual(expected, actual)


class CloneTests(CalculatedTestCase):
    __meta__ = False

    def setUp(self, cls=Clone):
        super(CloneTests, self).setUp(cls)

    def calculate(self, field):
        return field.render()


class ElementCountTests(CalculatedTestCase):

    __meta__ = False

    def setUp(self, cls=ElementCount):
        super(ElementCountTests, self).setUp(cls)
        self.length = 32
        self.bit_field = BitField(value=0, length=self.length)

    def get_default_field(self, fuzzable=False):
        return self.cls(self.depends_on_name, length=self.length, fuzzable=fuzzable)

    def calculate(self, field):
        self.bit_field.set_current_value(len(field.get_rendered_fields()))
        return self.bit_field.render()

    def testContainerWithInternalContainer(self):
        container = Container(
            name=self.depends_on_name,
            fields=[
                String('abc'),
                String('def'),
                Container(
                    name='counts_as_one',
                    fields=[
                        String('ghi'),
                        String('jkl'),
                    ])
            ])
        field = self.get_default_field()
        full = Container([container, field])
        self.assertEqual(field.render(), self.calculate(container))
        del full

    def testInternalContainer(self):
        internal_container = Container(
            name=self.depends_on_name,
            fields=[
                String('ghi'),
                String('jkl'),
            ])
        container = Container(
            name='this_doesnt_count',
            fields=[
                String('abc'),
                String('def'),
                internal_container
            ])
        field = self.get_default_field()
        full = Container([container, field])
        self.assertEqual(field.render(), self.calculate(internal_container))
        del full


class IndexOfTestCase(CalculatedTestCase):

    __meta__ = False

    def setUp(self, cls=IndexOf):
        super(IndexOfTestCase, self).setUp(cls)
        self.length = 32
        self.bit_field = BitField(value=0, length=self.length)

    def get_default_field(self, fuzzable=False):
        return self.cls(self.depends_on_name, length=self.length, fuzzable=fuzzable)

    def calculate(self, field):
        rendered = field._enclosing.get_rendered_fields()
        if field in rendered:
            value = rendered.index(field)
        else:
            value = len(rendered)
        self.bit_field.set_current_value(value)
        return self.bit_field.render()

    def _testCorrectIndex(self, expected_index):
        field_list = [String('%d' % i) for i in range(20)]
        field_list[expected_index] = self.get_original_field()
        uut = self.get_default_field()
        t = Container(name='level1', fields=[uut, Container(name='level2', fields=field_list)])
        rendered = uut.render().tobytes()
        result = unpack('>I', rendered)[0]
        self.assertEqual(result, expected_index)
        del t

    def testCorrectIndexFirst(self):
        self._testCorrectIndex(0)

    def testCorrectIndexMiddle(self):
        self._testCorrectIndex(10)

    def testCorrectIndexLast(self):
        self._testCorrectIndex(19)

    def testFieldNotRenderedAlone(self):
        expected_index = 0
        uut = self.get_default_field()
        the_field = Static(name=self.depends_on_name, value='')
        t = Container(name='level1', fields=[uut, Container(name='level2', fields=the_field)])
        rendered = uut.render().tobytes()
        result = unpack('>I', rendered)[0]
        self.assertEqual(result, expected_index)
        del t

    def testFieldNotRenderedWithOtherFields(self):
        expected_index = 3
        uut = self.get_default_field()
        fields = [
            Static(name=self.depends_on_name, value=''),
            Static('field1'),
            Static('field2'),
            Static('field3'),
        ]
        t = Container(name='level1', fields=[uut, Container(name='level2', fields=fields)])
        rendered = uut.render().tobytes()
        result = unpack('>I', rendered)[0]
        self.assertEqual(result, expected_index)
        del t



class SizeTests(CalculatedTestCase):
    __meta__ = False

    def setUp(self, cls=Size, length=32):
        super(SizeTests, self).setUp(cls)
        self.bit_field = BitField(value=0, length=length)
        self.length = length

    def get_default_field(self, length=None, calc_func=None, fuzzable=False):
        if length is None:
            length = self.length
        if calc_func is None:
            return self.cls(self.depends_on_name, length=length, fuzzable=fuzzable)
        else:
            return self.cls(self.depends_on_name, length=length, calc_func=calc_func, fuzzable=fuzzable)

    def calculate(self, field, calc_func=None):
        value = field.render()
        if calc_func:
            val = calc_func(value)
        else:
            val = len(value.bytes)
        self.bit_field.set_current_value(val)
        return self.bit_field.render()

    def test_custom_func_valid(self):
        def func(x):
            return len(x)
        original_field = self.get_original_field()
        calculated_field = self.get_default_field(calc_func=func)
        container = Container([original_field, calculated_field])
        expected = self.calculate(original_field, calc_func=func)
        actual = calculated_field.render()
        self.assertEqual(expected, actual)
        while container.mutate():
            expected = self.calculate(original_field, calc_func=func)
            actual = calculated_field.render()
            self.assertEqual(expected, actual)

    def test_invalid_length_0(self):
        with self.assertRaises(KittyException):
            self.cls(self.depends_on_name, length=0)

    def test_invalid_length_negative(self):
        with self.assertRaises(KittyException):
            self.cls(self.depends_on_name, length=-3)


class SizeInBytesTest(CalculatedTestCase):
    __meta__ = False

    def setUp(self, cls=SizeInBytes, length=32):
        super(SizeInBytesTest, self).setUp(cls)
        self.bit_field = BitField(value=0, length=length)
        self.length = length

    def get_default_field(self, fuzzable=False):
        return self.cls(self.depends_on_name, length=self.length, fuzzable=fuzzable)

    def calculate(self, field):
        value = field.render()
        self.bit_field.set_current_value(len(value.bytes))
        return self.bit_field.render()


class HashTests(CalculatedTestCase):
    __meta__ = True

    def setUp(self, cls=None, hasher=None):
        super(HashTests, self).setUp(cls)
        self.hasher = hasher

    def calculate(self, field):
        value = field.render()
        digest = self.hasher(value.bytes).digest()
        return Bits(bytes=digest)


class Md5Tests(HashTests):
    __meta__ = False

    def setUp(self):
        super(Md5Tests, self).setUp(Md5, hashlib.md5)


class Sha1Tests(HashTests):
    __meta__ = False

    def setUp(self):
        super(Sha1Tests, self).setUp(Sha1, hashlib.sha1)


class Sha224Tests(HashTests):
    __meta__ = False

    def setUp(self):
        super(Sha224Tests, self).setUp(Sha224, hashlib.sha224)


class Sha256Tests(HashTests):
    __meta__ = False

    def setUp(self):
        super(Sha256Tests, self).setUp(Sha256, hashlib.sha256)


class Sha384Tests(HashTests):
    __meta__ = False

    def setUp(self):
        super(Sha384Tests, self).setUp(Sha384, hashlib.sha384)


class Sha512Tests(HashTests):
    __meta__ = False

    def setUp(self):
        super(Sha512Tests, self).setUp(Sha512, hashlib.sha512)


class ValueTestCase(BaseTestCase):

    __meta__ = True
    default_value = None
    default_value_rendered = None

    def setUp(self, cls=None):
        super(ValueTestCase, self).setUp(cls)
        self.default_value = self.__class__.default_value
        self.default_value_rendered = self.__class__.default_value_rendered
        self.rendered_type = self.get_rendered_type()

    def get_rendered_type(self):
        return Bits

    def get_default_field(self, fuzzable=True):
        return self.cls(value=self.default_value, fuzzable=fuzzable)

    def bits_to_value(self, bits):
        '''
        default behavior: take the bytes
        '''
        return bits.bytes

    def _get_all_mutations(self, field, reset=True):
        res = []
        while field.mutate():
            res.append(field.render())
        if reset:
            field.reset()
        return res

    def _base_check(self, field):
        num_mutations = field.num_mutations()
        mutations = self._get_all_mutations(field)
        self.assertEqual(num_mutations, len(mutations))
        self.assertEqual(len(mutations), len(set(mutations)))
        mutations = self._get_all_mutations(field)
        self.assertEqual(num_mutations, len(mutations))
        self.assertEqual(len(mutations), len(set(mutations)))

    @metaTest
    def test_dummy_to_do(self):
        self.assertEqual(len(self.todo), 0)

    @metaTest
    def test_default_value(self):
        field = self.get_default_field()
        res = field.render()
        self.assertEqual(self.default_value_rendered, res)
        field.mutate()
        field.reset()
        res = field.render()
        self.assertEqual(self.default_value_rendered, res)

    @metaTest
    def test_mutate_all_different(self):
        field = self.get_default_field()
        mutations = self._get_all_mutations(field)
        self.assertEqual(len(set(mutations)), len(mutations))

    @metaTest
    def test_not_fuzzable(self):
        field = self.get_default_field(fuzzable=False)
        num_mutations = field.num_mutations()
        self.assertEqual(num_mutations, 0)
        rendered = field.render()
        as_val = self.bits_to_value(rendered)
        self.assertEqual(as_val, self.default_value)
        mutated = field.mutate()
        self.assertFalse(mutated)
        rendered = field.render()
        as_val = self.bits_to_value(rendered)
        self.assertEqual(as_val, self.default_value)
        field.reset()
        mutated = field.mutate()
        self.assertFalse(mutated)
        rendered = field.render()
        as_val = self.bits_to_value(rendered)
        self.assertEqual(as_val, self.default_value)

    @metaTest
    def test_num_mutations(self):
        field = self.get_default_field()
        num_mutations = field.num_mutations()
        self._check_mutation_count(field, num_mutations)

    @metaTest
    def test_same_result_when_same_params(self):
        field1 = self.get_default_field()
        field2 = self.get_default_field()
        res1 = self._get_all_mutations(field1)
        res2 = self._get_all_mutations(field2)
        self.assertListEqual(res1, res2)

    @metaTest
    def test_same_result_after_reset(self):
        field = self.get_default_field()
        res1 = self._get_all_mutations(field)
        res2 = self._get_all_mutations(field)
        self.assertListEqual(res1, res2)

    @metaTest
    def test_skip_zero(self):
        field = self.get_default_field(fuzzable=True)
        num_mutations = field.num_mutations()
        to_skip = 0
        expected_skipped = min(to_skip, num_mutations)
        expected_mutated = num_mutations - expected_skipped
        self._check_skip(field, to_skip, expected_skipped, expected_mutated)

    @metaTest
    def test_skip_one(self):
        field = self.get_default_field(fuzzable=True)
        num_mutations = field.num_mutations()
        to_skip = 1
        expected_skipped = min(to_skip, num_mutations)
        expected_mutated = num_mutations - expected_skipped
        self._check_skip(field, to_skip, expected_skipped, expected_mutated)

    @metaTest
    def test_skip_half(self):
        field = self.get_default_field(fuzzable=True)
        num_mutations = field.num_mutations()
        to_skip = num_mutations / 2
        expected_skipped = min(to_skip, num_mutations)
        expected_mutated = num_mutations - expected_skipped
        self._check_skip(field, to_skip, expected_skipped, expected_mutated)

    @metaTest
    def test_skip_exact(self):
        field = self.get_default_field(fuzzable=True)
        num_mutations = field.num_mutations()
        to_skip = num_mutations
        expected_skipped = min(to_skip, num_mutations)
        expected_mutated = num_mutations - expected_skipped
        self._check_skip(field, to_skip, expected_skipped, expected_mutated)

    @metaTest
    def test_skip_too_much(self):
        field = self.get_default_field(fuzzable=True)
        num_mutations = field.num_mutations()
        to_skip = num_mutations + 1
        expected_skipped = min(to_skip, num_mutations)
        expected_mutated = num_mutations - expected_skipped
        self._check_skip(field, to_skip, expected_skipped, expected_mutated)

    @metaTest
    def test_return_type_render_fuzzable(self):
        field = self.get_default_field(fuzzable=True)
        self.assertIsInstance(field.render(), self.rendered_type)
        field.mutate()
        self.assertIsInstance(field.render(), self.rendered_type)
        field.reset()
        self.assertIsInstance(field.render(), self.rendered_type)

    @metaTest
    def test_return_type_get_rendered_fuzzable(self):
        field = self.get_default_field(fuzzable=True)
        self.assertIsInstance(field.render(), self.rendered_type)
        field.mutate()
        self.assertIsInstance(field.render(), self.rendered_type)
        field.reset()
        self.assertIsInstance(field.render(), self.rendered_type)

    @metaTest
    def test_return_type_mutate_fuzzable(self):
        field = self.get_default_field(fuzzable=True)
        self.assertIsInstance(field.mutate(), types.BooleanType)
        field.reset()
        self.assertIsInstance(field.mutate(), types.BooleanType)

    @metaTest
    def test_return_type_render_not_fuzzable(self):
        field = self.get_default_field(fuzzable=False)
        self.assertIsInstance(field.render(), self.rendered_type)
        field.mutate()
        self.assertIsInstance(field.render(), self.rendered_type)
        field.reset()
        self.assertIsInstance(field.render(), self.rendered_type)

    @metaTest
    def test_return_type_get_rendered_not_fuzzable(self):
        field = self.get_default_field(fuzzable=False)
        self.assertIsInstance(field.render(), self.rendered_type)
        field.mutate()
        self.assertIsInstance(field.render(), self.rendered_type)
        field.reset()
        self.assertIsInstance(field.render(), self.rendered_type)

    @metaTest
    def test_return_type_mutate_not_fuzzable(self):
        field = self.get_default_field(fuzzable=False)
        self.assertIsInstance(field.mutate(), types.BooleanType)
        field.reset()
        self.assertIsInstance(field.mutate(), types.BooleanType)

    @metaTest
    def test_hash_the_same_for_two_similar_objects(self):
        field1 = self.get_default_field()
        field2 = self.get_default_field()
        self.assertEqual(field1.hash(), field2.hash())

    @metaTest
    def test_hash_the_same_after_reset(self):
        field = self.get_default_field()
        hash_after_creation = field.hash()
        field.mutate()
        hash_after_mutate = field.hash()
        self.assertEqual(hash_after_creation, hash_after_mutate)
        field.reset()
        hash_after_reset = field.hash()
        self.assertEqual(hash_after_creation, hash_after_reset)
        while field.mutate():
            hash_after_mutate_all = field.hash()
            self.assertEqual(hash_after_creation, hash_after_mutate_all)
            field.render()
            hash_after_render_all = field.hash()
            self.assertEqual(hash_after_creation, hash_after_render_all)

    @metaTest
    def testGetRenderedFields(self):
        field = self.get_default_field()
        field_list = [field]
        self.assertEqual(field.get_rendered_fields(), field_list)
        while field.mutate():
            if len(field.render()):
                self.assertEqual(field.get_rendered_fields(), field_list)
            else:
                self.assertEqual(field.get_rendered_fields(), [])

    def _check_skip(self, field, to_skip, expected_skipped, expected_mutated):
        skipped = field.skip(to_skip)
        self.assertEqual(expected_skipped, skipped)
        mutated = 0
        while field.mutate():
            mutated += 1
        self.assertEqual(expected_mutated, mutated)
        field.reset()
        skipped = field.skip(to_skip)
        self.assertEqual(expected_skipped, skipped)
        mutated = 0
        while field.mutate():
            mutated += 1
        self.assertEqual(expected_mutated, mutated)

    def _check_mutation_count(self, field, expected_num_mutations):
        num_mutations = field.num_mutations()
        self.assertEqual(num_mutations, expected_num_mutations)
        mutation_count = 0
        while field.mutate():
            mutation_count += 1
        self.assertEqual(mutation_count, expected_num_mutations)


class StringTests(ValueTestCase):

    __meta__ = False
    default_value = 'kitty'
    default_value_rendered = Bits(bytes=default_value)

    def setUp(self, cls=String):
        super(StringTests, self).setUp(cls)

    def test_max_size_num_mutations(self):
        max_size = 35
        nm_field = self.cls(value=self.default_value)
        excepted_mutation_count = 0
        while nm_field.mutate():
            res = nm_field.render().bytes
            if len(res) <= max_size:
                excepted_mutation_count += 1
        field = self.cls(value='kitty', max_size=max_size)
        num_mutations = field.num_mutations()
        self.assertEqual(excepted_mutation_count, num_mutations)
        self._check_mutation_count(field, excepted_mutation_count)

    def test_max_size_mutations(self):
        max_size = 35
        max_size_in_bits = max_size * 8
        nm_field = self.cls(value=self.default_value)
        all_mutations = self._get_all_mutations(nm_field)
        field = self.cls(value=self.default_value, max_size=max_size)
        mutations = self._get_all_mutations(field)
        for mutation in all_mutations:
            if len(mutation) > max_size_in_bits:
                self.assertNotIn(mutation, mutations)
            else:
                self.assertIn(mutation, mutations)


class DelimiterTests(StringTests):

    __meta__ = False
    default_value = 'kitty'
    default_value_rendered = Bits(bytes=default_value)

    def setUp(self, cls=Delimiter):
        super(DelimiterTests, self).setUp(cls)


class DynamicTests(ValueTestCase):

    __meta__ = False
    default_value = 'kitty'
    default_value_rendered = Bits(bytes=default_value)

    def setUp(self, cls=Dynamic):
        super(DynamicTests, self).setUp(cls)
        self.key_exists = 'exists'
        self.value_exists = 'value'
        self.key_not_exist = 'not exist'
        self.default_session_data = {
            self.key_exists: self.value_exists
        }

    def get_default_field(self, fuzzable=True):
        return self.cls(key='my_key', default_value=self.default_value, length=len(self.default_value), fuzzable=fuzzable)

    def test_session_data_not_fuzzable(self):
        field = self.cls(key=self.key_exists, default_value=self.default_value)
        self.assertEqual(self.default_value_rendered, field.render())
        field.set_session_data(self.default_session_data)
        self.assertEqual(Bits(bytes=self.value_exists), field.render())
        self.assertEqual(Bits(bytes=self.value_exists), field.render())

    def test_session_data_not_fuzzable_after_reset(self):
        field = self.cls(key=self.key_exists, default_value=self.default_value)
        self.assertEqual(self.default_value_rendered, field.render())
        field.set_session_data(self.default_session_data)
        self.assertEqual(Bits(bytes=self.value_exists), field.render())
        field.reset()
        self.assertEqual(self.default_value_rendered, field.render())

    def test_session_data_not_fuzzable_data_change_key_exists(self):
        field = self.cls(key=self.key_exists, default_value=self.default_value)
        self.assertEqual(self.default_value_rendered, field.render())
        field.set_session_data(self.default_session_data)
        self.assertEqual(Bits(bytes=self.value_exists), field.render())
        new_val = 'new value'
        field.set_session_data({self.key_exists: new_val})
        self.assertEqual(Bits(bytes=new_val), field.render())

    def test_session_data_not_fuzzable_data_change_key_not_exist(self):
        field = self.cls(key=self.key_exists, default_value=self.default_value)
        self.assertEqual(self.default_value_rendered, field.render())
        field.set_session_data(self.default_session_data)
        self.assertEqual(Bits(bytes=self.value_exists), field.render())
        new_val = 'new value'
        field.set_session_data({self.key_not_exist: new_val})
        self.assertEqual(Bits(bytes=self.value_exists), field.render())

    def test_session_data_fuzzable_after_reset(self):
        field = self.cls(key=self.key_exists, default_value=self.default_value, length=len(self.default_value), fuzzable=True)
        self.assertEqual(self.default_value_rendered, field.render())
        field.set_session_data(self.default_session_data)
        self.assertEqual(Bits(bytes=self.value_exists), field.render())
        field.reset()
        self.assertEqual(self.default_value_rendered, field.render())

    def test_session_data_fuzzable_data_change_key_exists(self):
        field = self.cls(key=self.key_exists, default_value=self.default_value, length=len(self.default_value), fuzzable=True)
        self.assertEqual(self.default_value_rendered, field.render())
        field.set_session_data(self.default_session_data)
        self.assertEqual(Bits(bytes=self.value_exists), field.render())
        new_val = 'new value'
        field.set_session_data({self.key_exists: new_val})
        self.assertEqual(Bits(bytes=new_val), field.render())

    def test_session_data_fuzzable_data_change_key_not_exist(self):
        field = self.cls(key=self.key_exists, default_value=self.default_value, length=len(self.default_value), fuzzable=True)
        self.assertEqual(self.default_value_rendered, field.render())
        field.set_session_data(self.default_session_data)
        self.assertEqual(Bits(bytes=self.value_exists), field.render())
        new_val = 'new value'
        field.set_session_data({self.key_not_exist: new_val})
        self.assertEqual(Bits(bytes=self.value_exists), field.render())


class RandomBitsTests(ValueTestCase):

    __meta__ = False
    default_value = 'kitty'
    default_unused_bits = 3
    default_value_rendered = Bits(bytes=default_value)[:-3]

    def setUp(self, cls=RandomBits):
        super(RandomBitsTests, self).setUp(cls)

    def get_default_field(self, fuzzable=True):
        return self.cls(value=self.default_value, min_length=5, max_length=10, unused_bits=self.default_unused_bits, fuzzable=fuzzable)

    def test_not_fuzzable(self):
        field = self.get_default_field(fuzzable=False)
        num_mutations = field.num_mutations()
        self.assertEqual(num_mutations, 0)
        rendered = field.render()
        self.assertEqual(rendered, self.default_value_rendered)
        mutated = field.mutate()
        self.assertFalse(mutated)
        rendered = field.render()
        self.assertEqual(rendered, self.default_value_rendered)
        field.reset()
        mutated = field.mutate()
        self.assertFalse(mutated)
        rendered = field.render()
        self.assertEqual(rendered, self.default_value_rendered)

    def test_no_step_num_mutations(self):
        param_num_mutations = 100
        field = self.cls(value=self.default_value, min_length=10, max_length=20, unused_bits=3, num_mutations=param_num_mutations)
        self._check_mutation_count(field, param_num_mutations)
        field.reset()
        self._check_mutation_count(field, param_num_mutations)

    def test_no_step_sizes(self):
        min_length = 10
        max_length = 100
        field = self.cls(value=self.default_value, min_length=min_length, max_length=max_length, unused_bits=self.default_unused_bits)
        while field.mutate():
            rendered = field.render()
            self.assertGreaterEqual(len(rendered), min_length)
            self.assertLessEqual(len(rendered), max_length)

    def test_no_step_min_negative(self):
        with self.assertRaises(KittyException):
            self.cls(value=self.default_value, min_length=-1, max_length=4)

    def test_no_step_max_negative(self):
        with self.assertRaises(KittyException):
            self.cls(value=self.default_value, min_length=-2, max_length=-1)

    def test_no_step_max_is_0(self):
        with self.assertRaises(KittyException):
            self.cls(value=self.default_value, min_length=0, max_length=0)

    def test_no_step_min_bigger_than_max(self):
        with self.assertRaises(KittyException):
            self.cls(value=self.default_value, min_length=5, max_length=4)

    def test_no_step_randomness(self):
        min_length = 10
        max_length = 100
        field = self.cls(value=self.default_value, min_length=min_length, max_length=max_length, unused_bits=self.default_unused_bits)
        mutations = self._get_all_mutations(field)
        self.assertNotEqual(len(set(mutations)), 1)

    def test_seed_not_the_same(self):
        min_length = 10
        max_length = 100
        field1 = self.cls(value=self.default_value, seed=11111, min_length=min_length, max_length=max_length, unused_bits=self.default_unused_bits)
        field2 = self.cls(value=self.default_value, seed=22222, min_length=min_length, max_length=max_length, unused_bits=self.default_unused_bits)
        res1 = self._get_all_mutations(field1)
        res2 = self._get_all_mutations(field2)
        self.assertNotEqual(res1, res2)

    def test_step_num_mutations(self):
        min_length = 10
        max_length = 100
        step = 3
        excepted_num_mutations = (max_length - min_length) / step
        field = self.cls(value=self.default_value, min_length=min_length, max_length=max_length, unused_bits=7, step=step)
        self._check_mutation_count(field, excepted_num_mutations)
        field.reset()
        self._check_mutation_count(field, excepted_num_mutations)

    def test_step_sizes(self):
        min_length = 10
        max_length = 100
        step = 3
        field = self.cls(value=self.default_value, min_length=min_length, max_length=max_length, unused_bits=self.default_unused_bits, step=step)
        expected_length = min_length
        while field.mutate():
            rendered = field.render()
            self.assertEqual(len(rendered), expected_length)
            expected_length += step

    def test_step_min_negative(self):
        with self.assertRaises(KittyException):
            self.cls(value=self.default_value, min_length=-1, max_length=4, step=1)

    def test_step_max_negative(self):
        with self.assertRaises(KittyException):
            self.cls(value=self.default_value, min_length=-2, max_length=-1, step=1)

    def test_step_max_is_0(self):
        with self.assertRaises(KittyException):
            self.cls(value=self.default_value, min_length=0, max_length=0, step=1)

    def test_step_min_bigger_than_max(self):
        with self.assertRaises(KittyException):
            self.cls(value=self.default_value, min_length=5, max_length=4, step=1)

    def test_step_negative(self):
        with self.assertRaises(KittyException):
            self.cls(value=self.default_value, min_length=1, max_length=5, step=-1)

    def test_step_randomness(self):
        min_length = 10
        max_length = 100
        step = 5
        field = self.cls(value=self.default_value, min_length=min_length, max_length=max_length, unused_bits=self.default_unused_bits, step=step)
        mutations = self._get_all_mutations(field)
        self.assertNotEqual(len(set(mutations)), 1)


class RandomBytesTests(ValueTestCase):

    __meta__ = False
    default_value = 'kitty'
    default_value_rendered = Bits(bytes=default_value)

    def setUp(self, cls=RandomBytes):
        super(RandomBytesTests, self).setUp(cls)

    def get_default_field(self, fuzzable=True):
        return self.cls(value=self.default_value, min_length=5, max_length=10, fuzzable=fuzzable)

    def test_no_step_num_mutations(self):
        param_num_mutations = 100
        field = RandomBytes(value=self.default_value, min_length=10, max_length=20, num_mutations=param_num_mutations)
        self._check_mutation_count(field, param_num_mutations)
        field.reset()
        self._check_mutation_count(field, param_num_mutations)

    def test_no_step_sizes(self):
        min_length = 10
        max_length = 100
        field = RandomBytes(value=self.default_value, min_length=min_length, max_length=max_length)
        while field.mutate():
            rendered = field.render().bytes
            self.assertGreaterEqual(len(rendered), min_length)
            self.assertLessEqual(len(rendered), max_length)

    def test_no_step_min_negative(self):
        with self.assertRaises(KittyException):
            RandomBytes(value=self.default_value, min_length=-1, max_length=4)

    def test_no_step_max_negative(self):
        with self.assertRaises(KittyException):
            RandomBytes(value=self.default_value, min_length=-2, max_length=-1)

    def test_no_step_max_is_0(self):
        with self.assertRaises(KittyException):
            RandomBytes(value=self.default_value, min_length=0, max_length=0)

    def test_no_step_min_bigger_than_max(self):
        with self.assertRaises(KittyException):
            RandomBytes(value=self.default_value, min_length=5, max_length=4)

    def test_no_step_randomness(self):
        min_length = 10
        max_length = 100
        field = RandomBytes(value=self.default_value, min_length=min_length, max_length=max_length)
        mutations = self._get_all_mutations(field)
        self.assertNotEqual(len(set(mutations)), 1)

    def test_seed_not_the_same(self):
        min_length = 10
        max_length = 100
        field1 = RandomBytes(value=self.default_value, seed=11111, min_length=min_length, max_length=max_length)
        field2 = RandomBytes(value=self.default_value, seed=22222, min_length=min_length, max_length=max_length)
        res1 = self._get_all_mutations(field1)
        res2 = self._get_all_mutations(field2)
        self.assertNotEqual(res1, res2)

    def test_step_num_mutations(self):
        min_length = 10
        max_length = 100
        step = 3
        excepted_num_mutations = (max_length - min_length) / step
        field = RandomBytes(value=self.default_value, min_length=min_length, max_length=max_length, step=step)
        self._check_mutation_count(field, excepted_num_mutations)
        field.reset()
        self._check_mutation_count(field, excepted_num_mutations)

    def test_step_sizes(self):
        min_length = 10
        max_length = 100
        step = 3
        field = RandomBytes(value=self.default_value, min_length=min_length, max_length=max_length, step=step)
        expected_length = min_length
        while field.mutate():
            rendered = field.render().bytes
            self.assertEqual(len(rendered), expected_length)
            expected_length += step

    def test_step_min_negative(self):
        with self.assertRaises(KittyException):
            RandomBytes(value=self.default_value, min_length=-1, max_length=4, step=1)

    def test_step_max_negative(self):
        with self.assertRaises(KittyException):
            RandomBytes(value=self.default_value, min_length=-2, max_length=-1, step=1)

    def test_step_max_is_0(self):
        with self.assertRaises(KittyException):
            RandomBytes(value=self.default_value, min_length=0, max_length=0, step=1)

    def test_step_min_bigger_than_max(self):
        with self.assertRaises(KittyException):
            RandomBytes(value=self.default_value, min_length=5, max_length=4, step=1)

    def test_step_negative(self):
        with self.assertRaises(KittyException):
            RandomBytes(value=self.default_value, min_length=1, max_length=5, step=-1)

    def test_step_randomness(self):
        min_length = 10
        max_length = 100
        step = 5
        field = RandomBytes(value=self.default_value, min_length=min_length, max_length=max_length, step=step)
        mutations = self._get_all_mutations(field)
        self.assertNotEqual(len(set(mutations)), 1)


class StaticTests(ValueTestCase):

    __meta__ = False
    default_value = 'kitty'
    default_value_rendered = Bits(bytes=default_value)

    def setUp(self, cls=Static):
        super(StaticTests, self).setUp(cls)

    def test_num_mutations_0(self):
        field = Static(value=self.default_value)
        num_mutations = field.num_mutations()
        self.assertEqual(num_mutations, 0)
        self._check_mutation_count(field, num_mutations)
        field.reset()
        self._check_mutation_count(field, num_mutations)

    def get_default_field(self, fuzzable=True):
        return Static(value=self.default_value)


class GroupTests(ValueTestCase):

    __meta__ = False
    default_value = 'group 1'
    default_value_rendered = Bits(bytes=default_value)
    default_values = [default_value, 'group 2', 'group 3', 'group 4', 'group 5']

    def setUp(self, cls=Group):
        super(GroupTests, self).setUp(cls)
        self.default_values = self.__class__.default_values

    def get_default_field(self, fuzzable=True):
        return self.cls(values=self.default_values, fuzzable=fuzzable)

    def test_mutations(self):
        field = self.get_default_field()
        mutations = self._get_all_mutations(field)
        self.assertListEqual([Bits(bytes=x) for x in self.default_values], mutations)
        mutations = self._get_all_mutations(field)
        self.assertListEqual([Bits(bytes=x) for x in self.default_values], mutations)


class BitFieldTests(ValueTestCase):

    __meta__ = False
    default_value = 500
    default_length = 15
    default_value_rendered = Bits('uint:%d=%d' % (default_length, default_value))

    def setUp(self, cls=BitField):
        super(BitFieldTests, self).setUp(cls)
        self.default_length = self.__class__.default_length

    def get_rendered_type(self):
        return Bits

    def get_default_field(self, fuzzable=True):
        return self.cls(value=self.default_value, length=self.default_length, fuzzable=fuzzable)

    def bits_to_value(self, bits):
        '''
        BitField returns a tuple. so just give the value...
        '''
        return bits.uint

    def test_length_negative(self):
        with self.assertRaises(KittyException):
            BitField(value=self.default_value, length=-1)

    def test_length_zero(self):
        with self.assertRaises(KittyException):
            BitField(value=self.default_value, length=0)

    def test_length_very_small(self):
        self._base_check(BitField(value=1, length=1))

    def test_length_too_small_for_value_signed(self):
        with self.assertRaises(KittyException):
            BitField(value=64, length=7, signed=True)

    def test_length_too_small_for_value_unsigned(self):
        with self.assertRaises(KittyException):
            BitField(value=64, length=6, signed=False)

    def test_length_too_small_for_max_value(self):
        with self.assertRaises(KittyException):
            BitField(value=10, length=5, signed=True, max_value=17)

    def test_length_very_large(self):
        field = BitField(value=1, length=1)
        self._base_check(field)

    def test_length_non_byte_aligned_unsigned(self):
        signed = False
        self._base_check(BitField(value=10, length=7, signed=signed))
        self._base_check(BitField(value=10, length=14, signed=signed))
        self._base_check(BitField(value=10, length=15, signed=signed))
        self._base_check(BitField(value=10, length=16, signed=signed))
        self._base_check(BitField(value=10, length=58, signed=signed))
        self._base_check(BitField(value=10, length=111, signed=signed))

    def test_length_non_byte_aligned_signed(self):
        signed = True
        self._base_check(BitField(value=10, length=7, signed=signed))
        self._base_check(BitField(value=10, length=14, signed=signed))
        self._base_check(BitField(value=10, length=15, signed=signed))
        self._base_check(BitField(value=10, length=16, signed=signed))
        self._base_check(BitField(value=10, length=58, signed=signed))
        self._base_check(BitField(value=10, length=111, signed=signed))

    def test_value_negative(self):
        self._base_check(BitField(value=-50, length=7, signed=True))


class AlignedBitTests(ValueTestCase):
    #
    # Ugly ? yes, but this way we avoid errors when they are not needed...
    #
    __meta__ = True
    default_value = 500
    default_length = 16
    default_value_rendered = Bits('uint:%d=%d' % (default_length, default_value))

    def setUp(self, cls=None):
        super(AlignedBitTests, self).setUp(cls)
        self.default_length = self.__class__.default_length

    def get_rendered_type(self):
        return Bits

    def get_default_field(self, fuzzable=True):
        return self.cls(value=self.default_value, fuzzable=fuzzable)

    def bits_to_value(self, bits):
        return bits.uint

    @metaTest
    def test_max_value(self):
        max_value = self.default_value + 10
        field = self.cls(value=self.default_value, max_value=max_value)
        mutations = self._get_all_mutations(field)
        for mutation in mutations:
            self.assertGreaterEqual(max_value, self.bits_to_value(mutation))

    @metaTest
    def test_min_value(self):
        min_value = self.default_value - 10
        field = self.cls(value=self.default_value, min_value=min_value)
        mutations = self._get_all_mutations(field)
        for mutation in mutations:
            self.assertLessEqual(min_value, self.bits_to_value(mutation))

    @metaTest
    def test_min_max_value(self):
        min_value = self.default_value - 10
        max_value = self.default_value + 10
        field = self.cls(value=self.default_value, min_value=min_value, max_value=max_value)
        mutations = self._get_all_mutations(field)
        for mutation in mutations:
            self.assertLessEqual(min_value, self.bits_to_value(mutation))
            self.assertGreaterEqual(max_value, self.bits_to_value(mutation))


class SignedAlignedBitTests(AlignedBitTests):

    __meta__ = True

    def bits_to_value(self, bits):
        return bits.int


class SInt8Tests(SignedAlignedBitTests):

    __meta__ = False
    default_value = 50
    default_length = 8
    default_value_rendered = Bits('int:%d=%d' % (default_length, default_value))

    def setUp(self, cls=SInt8):
        super(SInt8Tests, self).setUp(cls)


class SInt16Tests(SignedAlignedBitTests):

    __meta__ = False
    default_value = 0x1000
    default_length = 16
    default_value_rendered = Bits('int:%d=%d' % (default_length, default_value))

    def setUp(self, cls=SInt16):
        super(SInt16Tests, self).setUp(cls)


class SInt32Tests(SignedAlignedBitTests):

    __meta__ = False
    default_value = 0x12345678
    default_length = 32
    default_value_rendered = Bits('int:%d=%d' % (default_length, default_value))

    def setUp(self, cls=SInt32):
        super(SInt32Tests, self).setUp(cls)


class SInt64Tests(SignedAlignedBitTests):

    __meta__ = False
    default_value = 0x1122334455667788
    default_length = 64
    default_value_rendered = Bits('int:%d=%d' % (default_length, default_value))

    def setUp(self, cls=SInt64):
        super(SInt64Tests, self).setUp(cls)


class UnsignedAlignedBitTests(AlignedBitTests):

    __meta__ = True

    def bits_to_value(self, bits):
        return bits.uint


class UInt8Tests(UnsignedAlignedBitTests):

    __meta__ = False
    default_value = 50
    default_length = 8
    default_value_rendered = Bits('uint:%d=%d' % (default_length, default_value))

    def setUp(self, cls=UInt8):
        super(UInt8Tests, self).setUp(cls)


class UInt16Tests(UnsignedAlignedBitTests):

    __meta__ = False
    default_value = 0x1000
    default_length = 16
    default_value_rendered = Bits('uint:%d=%d' % (default_length, default_value))

    def setUp(self, cls=UInt16):
        super(UInt16Tests, self).setUp(cls)


class UInt32Tests(UnsignedAlignedBitTests):

    __meta__ = False
    default_value = 0x12345678
    default_length = 32
    default_value_rendered = Bits('uint:%d=%d' % (default_length, default_value))

    def setUp(self, cls=UInt32):
        super(UInt32Tests, self).setUp(cls)


class UInt64Tests(UnsignedAlignedBitTests):

    __meta__ = False
    default_value = 0x1122334455667788
    default_length = 64
    default_value_rendered = Bits('uint:%d=%d' % (default_length, default_value))

    def setUp(self, cls=UInt64):
        super(UInt64Tests, self).setUp(cls)
