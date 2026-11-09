# Automatically deactivate gift cards that have been used up

Support keeps getting tickets from customers who see fully spent cards still listed as active, and the active/inactive filter in the dashboard is useless for finding cards that still have money on them. A gift card should be switched to inactive (`is_active = False`) as soon as its balance reaches zero, and cards with a balance above zero must be left as they are.

This has to hold for both ways a balance can go down to zero: a customer paying with the card at checkout (the function `charge_gift_card` in `saleor/giftcard/gateway.py`, which deducts the authorized amount from the card) and staff using the `giftCardBalanceAdjust` mutation, including when the requested deduction is larger than the remaining balance and the balance is clamped to zero. Nothing needs to happen when a card is later topped up again; staff can reactivate it with the existing `giftCardActivate` mutation.
