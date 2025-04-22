from datetime import datetime
from dataclasses import fields
from kuru_sdk.types import Order, MarketParams


def format_orders_list_payload(payload) -> list[Order]:
    orders_list: list[Order] = []
    if payload and payload.get('success'):
        raw_orders_data = payload.get('data', {}).get('data', [])
        for order_data in raw_orders_data:
            # amount of order_data keys should be equal to the amount of Order fields
            raw_obj_keys_length = len(order_data.keys())
            order_field_keys_length = len(fields(Order))
            assert raw_obj_keys_length == order_field_keys_length, \
                    f"Amount of order_data keys ({raw_obj_keys_length}) does not match " \
                    f"the amount of Order fields ({order_field_keys_length})"
            
            order = Order(
                market_address=order_data['marketAddress'],
                order_id=int(order_data['orderid']),
                owner=order_data['owner'],
                size=order_data['size'],
                price=order_data['price'],
                is_buy=bool(order_data['isbuy']),
                remaining_size=order_data['remainingsize'],
                is_canceled=bool(order_data['iscanceled']),
                block_number=order_data['blocknumber'],
                tx_index=order_data['txindex'],
                log_index=order_data['logindex'],
                transaction_hash=order_data['transactionhash'],
                trigger_time=datetime.strptime(order_data['triggertime'], '%Y-%m-%dT%H:%M:%S.%fZ'),
                total_size=order_data['total_size'],
            )
            orders_list.append(order)
    return orders_list

