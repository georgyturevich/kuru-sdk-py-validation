import json
import unittest
from datetime import datetime

from kuru_sdk.types import Order
from lib.utils.format import format_orders_list_payload


class TestFormatOrdersList(unittest.TestCase):
    def test_format_orders_list_payload(self):
        # Test payload as provided
        payload_json = '''
        {
            "success": true,
            "code": 200,
            "timestamp": 1744719149373,
            "data": {
                "data": [
                    {
                        "marketAddress": "0x05e6f736b5dedd60693fa806ce353156a1b73cf3",
                        "orderid": 589,
                        "owner": "0x6650514f909d2ab6a6a6647464e45f9f9d81f1da",
                        "size": "10000000000000",
                        "price": "200",
                        "isbuy": true,
                        "remainingsize": "10000000000000",
                        "iscanceled": false,
                        "blocknumber": "12304669",
                        "txindex": "34",
                        "logindex": "105",
                        "transactionhash": "0xb88568900a2dbcb721cff8d11c24df6d80d52ca6cc0a86317e5436995bdce690",
                        "triggertime": "2025-04-15T10:06:32.123Z",
                        "total_size": "10000000000000"
                    }
                ],
                "pagination": {
                    "total": 4,
                    "page": 1,
                    "pageSize": 100
                }
            }
        }
        '''
        
        # Parse the JSON string into a Python dictionary
        payload = json.loads(payload_json)
        
        # Call the function with the test payload
        result = format_orders_list_payload(payload)
        
        # Assertions
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        
        order = result[0]
        self.assertIsInstance(order, Order)
        
        # Verify all fields were correctly parsed
        self.assertEqual(order.market_address, "0x05e6f736b5dedd60693fa806ce353156a1b73cf3")
        self.assertEqual(order.order_id, 589)
        self.assertEqual(order.owner, "0x6650514f909d2ab6a6a6647464e45f9f9d81f1da")
        self.assertEqual(order.size, "10000000000000")
        self.assertEqual(order.price, "200")
        self.assertTrue(order.is_buy)
        self.assertEqual(order.remaining_size, "10000000000000")
        self.assertFalse(order.is_canceled)
        self.assertEqual(order.block_number, "12304669")
        self.assertEqual(order.tx_index, "34")
        self.assertEqual(order.log_index, "105")
        self.assertEqual(order.transaction_hash, "0xb88568900a2dbcb721cff8d11c24df6d80d52ca6cc0a86317e5436995bdce690")
        self.assertEqual(order.trigger_time, datetime.strptime("2025-04-15T10:06:32.123Z", '%Y-%m-%dT%H:%M:%S.%fZ'))
        self.assertEqual(order.total_size, "10000000000000")

    def test_format_orders_list_payload_empty(self):
        # Test with empty payload
        result = format_orders_list_payload(None)
        self.assertEqual(result, [])
        
        # Test with unsuccessful response
        result = format_orders_list_payload({"success": False})
        self.assertEqual(result, [])
        
        # Test with empty data
        result = format_orders_list_payload({"success": True, "data": {}})
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main() 