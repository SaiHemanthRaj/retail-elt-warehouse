# Data provenance
All rows are synthetic and generated specifically for this portfolio with Python's
random.Random(41). They contain no real customers or employer data. Dataset license: CC0 1.0.
Initial batch: 1,200 order lines, 60 customers, 15 products, four stores.
Second batch: 30 corrected orders, 20 late arrivals, five stale updates.
Six customers change region on September 10. Late orders on September 5 keep the old region.
An order is one line item here; a real multi-line order needs (order_id,line_id) as its grain.
Money is integer cents in one currency. updated_at is naive UTC; customer effective dates are calendar dates.
