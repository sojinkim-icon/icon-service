# -*- coding: utf-8 -*-

# Copyright 2018 ICON Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""IconScoreEngine testcase
"""

import unittest
from typing import List
from unittest.mock import Mock


from iconservice.iconscore.icon_score_base import eventlog, IconScoreBase, IconScoreDatabase, external
from iconservice.base.address import Address, AddressPrefix
from iconservice.base.exception import EventLogException, ScoreErrorException
from iconservice.icon_constant import DATA_BYTE_ORDER, ICX_TRANSFER_EVENT_LOG
from iconservice.iconscore.icon_score_context import ContextContainer, \
    IconScoreContext, IconScoreContextType, IconScoreFuncType
from iconservice.iconscore.icon_score_step import IconScoreStepCounter
from iconservice.icx import IcxEngine
from iconservice.utils import int_to_bytes
from iconservice.utils import to_camel_case
from iconservice.utils.bloom import BloomFilter


class TestEventlog(unittest.TestCase):
    def setUp(self):
        address = Address.from_data(AddressPrefix.CONTRACT, b'address')
        db = Mock(spec=IconScoreDatabase)
        db.attach_mock(address, 'address')
        context = IconScoreContext()
        event_logs = Mock(spec=list)
        traces = Mock(spec=list)
        step_counter = Mock(spec=IconScoreStepCounter)
        logs_bloom = BloomFilter()

        context.type = IconScoreContextType.INVOKE
        context.func_type = IconScoreFuncType.WRITABLE
        context.event_logs = event_logs
        context.traces = traces
        context.logs_bloom = logs_bloom
        context.step_counter = step_counter
        context.icon_score_manager = Mock()
        context.icon_score_manager.get_owner = Mock()
        context.internal_call.icx_engine = Mock(spec=IcxEngine)
        ContextContainer._push_context(context)

        self._mock_score = EventlogScore(db)

    def tearDown(self):
        ContextContainer._clear_context()

    def test_call_event(self):
        context = ContextContainer._get_context()

        name = "name"
        address = Address.from_data(AddressPrefix.EOA, b'address')
        age = 10
        phone_number = "000"

        # Tests simple event emit
        self._mock_score.ZeroIndexEvent(name, address, age)
        context.event_logs.append.assert_called()
        event_log = context.event_logs.append.call_args[0][0]
        self.assertEqual(1, len(event_log.indexed))
        self.assertEqual(3, len(event_log.data))

        # This event has a indexed parameter,
        # so the list of indexed Should have 2 items
        self._mock_score.OneIndexEvent(name, address, age)
        context.event_logs.append.assert_called()
        event_log = context.event_logs.append.call_args[0][0]
        self.assertEqual(2, len(event_log.indexed))
        self.assertEqual(2, len(event_log.data))

        zero_event_bloom_data = \
            int(0).to_bytes(1, DATA_BYTE_ORDER) + \
            'ZeroIndexEvent(str,Address,int)'.encode('utf-8')
        self.assertIn(zero_event_bloom_data, context.logs_bloom)

        one_event_bloom_data = \
            int(0).to_bytes(1, DATA_BYTE_ORDER) + \
            'OneIndexEvent(str,Address,int)'.encode('utf-8')
        self.assertIn(one_event_bloom_data, context.logs_bloom)

        name_bloom_data = int(1).to_bytes(1, DATA_BYTE_ORDER) + name.encode('utf-8')
        self.assertIn(name_bloom_data, context.logs_bloom)

        # This event is declared 3 indexed_count,
        # but it accept only 2 arguments.
        self.assertRaises(EventLogException, self._mock_score.ThreeIndexEvent,
                          name, address)

        # This event is declared 4 indexed_count
        self.assertRaises(EventLogException, self._mock_score.FourIndexEvent,
                          name, address, age, phone_number)

    def test_call_event_kwarg(self):
        context = ContextContainer._get_context()

        name = "name"
        address = Address.from_data(AddressPrefix.EOA, b'address')
        age = 10

        # Call with ordered arguments
        self._mock_score.OneIndexEvent(name, address, age)
        context.event_logs.append.assert_called()
        event_log_ordered_args = context.event_logs.append.call_args[0][0]

        # Call with ordered arguments and keyword arguments
        self._mock_score.OneIndexEvent(
            name, age=age, address=address)
        context.event_logs.append.assert_called()
        event_log_keyword_args = context.event_logs.append.call_args[0][0]

        self.assertEqual(event_log_ordered_args.score_address,
                         event_log_keyword_args.score_address)
        self.assertEqual(event_log_ordered_args.indexed,
                         event_log_keyword_args.indexed)
        self.assertEqual(event_log_ordered_args.data,
                         event_log_keyword_args.data)

        one_event_bloom_data = \
            int(0).to_bytes(1, DATA_BYTE_ORDER) + \
            'OneIndexEvent(str,Address,int)'.encode('utf-8')
        self.assertIn(one_event_bloom_data, context.logs_bloom)

        name_bloom_data = int(1).to_bytes(1, DATA_BYTE_ORDER) + name.encode('utf-8')
        self.assertIn(name_bloom_data, context.logs_bloom)

    def test_call_event_mismatch_arg(self):
        context = ContextContainer._get_context()

        name = "name"
        address = Address.from_data(AddressPrefix.EOA, b'address')
        age = "10"
        # The hint of 'age' is int type but argument is str type

        self.assertRaises(ScoreErrorException, self._mock_score.OneIndexEvent,
                          name, address, age)

        one_event_bloom_data = \
            int(0).to_bytes(1, DATA_BYTE_ORDER) + \
            'OneIndexEvent(str,Address,int)'.encode('utf-8')
        self.assertNotIn(one_event_bloom_data, context.logs_bloom)

        name_bloom_data = int(1).to_bytes(1, DATA_BYTE_ORDER) + name.encode('utf-8')
        self.assertNotIn(name_bloom_data, context.logs_bloom)

    def test_address_index_event(self):
        context = ContextContainer._get_context()

        address = Address.from_data(AddressPrefix.EOA, b'address')

        # Tests simple event emit
        self._mock_score.AddressIndexEvent(address)
        context.event_logs.append.assert_called()
        event_log = context.event_logs.append.call_args[0][0]
        self.assertEqual(2, len(event_log.indexed))
        self.assertEqual(0, len(event_log.data))

        event_bloom_data = \
            int(0).to_bytes(1, DATA_BYTE_ORDER) + \
            'AddressIndexEvent(Address)'.encode('utf-8')
        self.assertIn(event_bloom_data, context.logs_bloom)

        indexed_bloom_data = \
            int(1).to_bytes(1, DATA_BYTE_ORDER) + address.body
        self.assertIn(indexed_bloom_data, context.logs_bloom)

    def test_bool_index_event(self):
        context = ContextContainer._get_context()

        yes_no = True

        # Tests simple event emit
        self._mock_score.BoolIndexEvent(yes_no)
        context.event_logs.append.assert_called()
        event_log = context.event_logs.append.call_args[0][0]
        self.assertEqual(2, len(event_log.indexed))
        self.assertEqual(0, len(event_log.data))

        event_bloom_data = \
            int(0).to_bytes(1, DATA_BYTE_ORDER) + \
            'BoolIndexEvent(bool)'.encode('utf-8')
        self.assertIn(event_bloom_data, context.logs_bloom)

        indexed_bloom_data = \
            int(1).to_bytes(1, DATA_BYTE_ORDER) + int_to_bytes(yes_no)
        self.assertIn(indexed_bloom_data, context.logs_bloom)

    def test_int_index_event(self):
        context = ContextContainer._get_context()

        amount = 123456789

        # Tests simple event emit
        self._mock_score.IntIndexEvent(amount)
        context.event_logs.append.assert_called()
        event_log = context.event_logs.append.call_args[0][0]
        self.assertEqual(2, len(event_log.indexed))
        self.assertEqual(0, len(event_log.data))

        event_bloom_data = \
            int(0).to_bytes(1, DATA_BYTE_ORDER) + \
            'IntIndexEvent(int)'.encode('utf-8')
        self.assertIn(event_bloom_data, context.logs_bloom)

        indexed_bloom_data = \
            int(1).to_bytes(1, DATA_BYTE_ORDER) + int_to_bytes(amount)
        self.assertIn(indexed_bloom_data, context.logs_bloom)

    def test_bytes_index_event(self):
        context = ContextContainer._get_context()

        data = b'0123456789abc'

        # Tests simple event emit
        self._mock_score.BytesIndexEvent(data)
        context.event_logs.append.assert_called()
        event_log = context.event_logs.append.call_args[0][0]
        self.assertEqual(2, len(event_log.indexed))
        self.assertEqual(0, len(event_log.data))

        event_bloom_data = \
            int(0).to_bytes(1, DATA_BYTE_ORDER) + \
            'BytesIndexEvent(bytes)'.encode('utf-8')
        self.assertIn(event_bloom_data, context.logs_bloom)

        indexed_bloom_data = \
            int(1).to_bytes(1, DATA_BYTE_ORDER) + data
        self.assertIn(indexed_bloom_data, context.logs_bloom)

    def test_to_dict_camel(self):
        context = ContextContainer._get_context()

        address = Address.from_data(AddressPrefix.EOA, b'address')
        age = 10
        data = b'0123456789abc'

        self._mock_score.MixedEvent(b'i_data', address, age, data, 'text')
        context.event_logs.append.assert_called()
        event_log = context.event_logs.append.call_args[0][0]

        camel_dict = event_log.to_dict(to_camel_case)
        self.assertIn('scoreAddress', camel_dict)
        self.assertIn('indexed', camel_dict)
        self.assertIn('data', camel_dict)
        self.assertEqual(3, len(camel_dict['indexed']))
        self.assertEqual(3, len(camel_dict['data']))

    def test_event_log_on_readonly_method(self):
        context = ContextContainer._get_context()
        context.func_type = IconScoreFuncType.READONLY

        with self.assertRaises(EventLogException):
            self._mock_score.BoolIndexEvent(False)

    def test_reserved_event_log(self):
        context = ContextContainer._get_context()
        context.func_type = IconScoreFuncType.READONLY

        address = Address.from_data(AddressPrefix.EOA, b'address')
        with self.assertRaises(EventLogException):
            self._mock_score.ICXTransfer(address, address, 0)

    def test_icx_transfer_event(self):
        context = ContextContainer._get_context()

        address = Address.from_data(AddressPrefix.EOA, b'address')

        # Tests simple event emit
        self._mock_score.icx.send(address, 1)
        context.event_logs.append.assert_called()
        event_log = context.event_logs.append.call_args[0][0]
        self.assertEqual(4, len(event_log.indexed))
        self.assertEqual(ICX_TRANSFER_EVENT_LOG, event_log.indexed[0])
        self.assertEqual(0, len(event_log.data))

    def tearDown(self):
        self._mock_icon_score = None


class EventlogScore(IconScoreBase):

    def __init__(self, db: 'IconScoreDatabase') -> None:
        super().__init__(db)

    def on_install(self) -> None:
        pass

    def on_update(self) -> None:
        pass

    @eventlog
    def ZeroIndexEvent(self, name: str, address: 'Address', age: int):
        pass

    @eventlog(indexed=1)
    def OneIndexEvent(self, name: str, address: Address, age: int):
        pass

    @eventlog(indexed=3)
    def ThreeIndexEvent(self, name: str, address: Address):
        pass

    @eventlog(indexed=4)
    def FourIndexEvent(
            self, name: str, address: Address, age: int, phone_number: str):
        pass

    @eventlog(indexed=1)
    def AddressIndexEvent(self, address: Address):
        pass

    @eventlog(indexed=1)
    def BoolIndexEvent(self, yes_no: bool):
        pass

    @eventlog(indexed=1)
    def IntIndexEvent(self, amount: int):
        pass

    @eventlog(indexed=1)
    def BytesIndexEvent(self, data: bytes):
        pass

    @eventlog(indexed=2)
    def MixedEvent(self, i_data: bytes, address: Address, amount: int,
                   data: bytes, text: str):
        pass

    @eventlog(indexed=3)
    def ICXTransfer(self, from_: Address, to: Address, amount: int):
        pass

    @external
    def empty(self):
        pass
