# Copyright Google

# BSD License

import argparse
import copy
import csv
import datetime

class Lot(object):
  """Represents a buy with optional sell."""
  def __init__(self, count, symbol, description,
               buydate, basis,
               selldate = None,
               code = None,
               adjustment = None,
               proceeds = None,
               form_position = '',
               original_form_position = '',
               buy_lot = '',
               is_replacement = False):
    self.count = count
    self.symbol = symbol
    self.description = description
    self.buydate = buydate
    self.basis = basis
    # These may be None if it's just a buy:
    self.selldate = selldate
    self.code = code
    self.adjustment = adjustment
    self.proceeds = proceeds
    self.original_form_position = self.form_position = form_position
    self.buy_lot = buy_lot
    self.is_replacement = is_replacement

  @staticmethod
  def str_to_float(f):
    if f.startswith('$'): f = f[1:]
    f = f.replace(',', '')
    if f == '': f = '0'
    return float(f)

  @staticmethod
  def create_from_csv_row(row, buy_lot):
    if len(row) > 10 and row[10]:
      buy_lot = row[10]
    lot = Lot(int(row[0]), row[1], row[2],
              datetime.datetime.strptime(row[3].strip(), "%m/%d/%Y").date(),
              Lot.str_to_float(row[4]), buy_lot=buy_lot)
    if row[5]:
      lot.selldate = \
        datetime.datetime.strptime(row[5].strip(), "%m/%d/%Y").date()
      lot.proceeds = Lot.str_to_float(row[6])
      lot.code = row[7]
      lot.adjustment = Lot.str_to_float(row[8])
    lot.original_form_position = lot.form_position = row[9]
    is_replacement = False
    if len(row) > 11:
      is_replacement = not (row[11].lower() != 'true')
    lot.is_replacement = is_replacement
    return lot
  def acquition_match(self, that):
    return (self.count == that.count and
            self.symbol == that.symbol and
            self.description == that.description and
            self.buydate == that.buydate and
            self.basis == that.basis)
  def has_sell(self):
    return self.selldate is not None
  @staticmethod
  def csv_headers():
    return ['Count', 'Symbol', 'Description', 'Date Acquired',
            'Cost Basis', 'Date Sold', 'Proceeds', 'AdjCode',
            'Adjustment Amount', 'FormPosition', 'BuyLot', 'IsReplacement']
  def csv_row(self):
    # Rounds floats to 3 decimals, which is sufficient to show the rounding
    # that will occur when converting to a valid amount in cents.
    # This is just for cosmetic improvement. If this requires fixing, move to
    # a fixed-point arithmetic package.
    return [self.count, self.symbol, self.description or "%s %s" % (self.count, self.symbol),
            self.buydate.strftime('%m/%d/%Y'),
            round(self.basis, 3) if self.basis else None,
            None if self.selldate is None else \
            self.selldate.strftime('%m/%d/%Y'),
            round(self.proceeds, 3) if self.proceeds else None, self.code,
            round(self.adjustment, 3) if self.adjustment else None, self.form_position,
            self.buy_lot, 'True' if self.is_replacement else '']
  def __eq__(self, that):
    if not isinstance(that, self.__class__):
      return False
    return self.__dict__ == that.__dict__
  def __ne__(self, that):
    return not self.__eq__(that)
  def __str__(self):
    front = ("%2d %s (%s) acq: %s %8.03f" %
             (self.count, self.symbol, self.description,
              self.buydate, self.basis))
    sell = ""
    code = ""
    if self.selldate:
      sell = (" sell: %s %8.03f" %
              (self.selldate, self.proceeds))
    if self.code or self.adjustment:
      if self.adjustment:
        code = " [%1s %6.03f]" % (self.code, self.adjustment)
      else:
        code = " [%1s]" % (self.code)
    position = ''
    if self.form_position:
      position = " " + self.form_position
    replacement = ''
    if self.is_replacement:
      replacement = ' [IsRepl]'
    return front + sell + code + position + ' ' + self.buy_lot + replacement
  __repr__ = __str__

def save_lots(lots, filepath):
  # Write the lots out to the given file
  fd = open(filepath, 'w')
  writer = csv.writer(fd)
  writer.writerow(Lot.csv_headers())
  for lot in lots:
    writer.writerow(lot.csv_row())

def load_lots(filepath):
  reader = csv.reader(open(filepath))
  ret = []
  buy_num = 1
  for row in reader:
    if row[0] and row[0] == Lot.csv_headers()[0]:
      continue
    ret.append(Lot.create_from_csv_row(row, str(buy_num)))
    if ret[-1].buy_lot == str(buy_num):
      buy_num = buy_num + 1
  return ret

def merge_split_lots(lots):
  """Merge split lots back together, assuming lots is sorted with respect to
  original_form_position so only sequential records need to be merged."""

  out = []
  # First lot in new sequence
  prev = copy.copy(lots[0])
  for lot in lots[1:]:
    assert(prev.original_form_position <= lot.original_form_position)
    if lot.original_form_position == prev.original_form_position:
      assert(lot.symbol == prev.symbol)
      # buydate may be pushed back assert(lot.buydate == prev.buydate)
      # Merge previous and this one
      prev.count += lot.count
      prev.basis += lot.basis
      prev.proceeds += lot.proceeds
      prev.adjustment += lot.adjustment
      prev.buy_lot += '|' + lot.buy_lot
      assert(prev.code == "" or lot.code == "" or prev.code == lot.code)
      if lot.code:
        prev.code = lot.code
    else:
      # Loop has moved on to a different lot, finished with current
      out.append(prev)
      prev = copy.copy(lot)

  if prev:
    out.append(prev)

  return out

def adjust_for_dollar_rounding(lots):
  """Make wash sale gain be 0.0 even when amounts are individually rounded to full dollars.

  Because some tax packages will round (to $1) the cost basis, proceeds, and adjustment,
  the final amount after a wash sale may not be $0 but may be -1 or +1, leading
  to alerts or issues. Avoid this situation by nudging the adjustment amount up or down.
  """
  for lot in lots:
    if not lot.has_sell() or not lot.adjustment:
      continue

    # Do the minor adjustment only if the exact profit is zero. This may be
    # less than zero if the split lots have been merged, in which case it is
    # perfectly fine for total loss to be greater than the adjustment amount.
    # If no merging is done, then all wash sale lots have profit_actual == 0.0
    profit_exact = lot.proceeds - lot.basis + lot.adjustment
    profit = round(lot.proceeds) - round(lot.basis) + round(lot.adjustment)
    if abs(profit_exact) < 0.0000001 and profit != 0.0:
      #lot.adjustment -= profit # this is fine, a lower value can work too:
      lot.adjustment = round(lot.adjustment) - round(profit) - 0.5
      profit = round(lot.proceeds) - round(lot.basis) + round(lot.adjustment)
      assert(abs(profit) < .0000001)

def assert_lots_values(lots, merged=False, rounded_dollars=False):
  """Assert failure if the lots contain unexpected values.
  Example: adjustment value is outside expected range, and other tests."""

  # make sure all elements are unique
  id_list = [id(lot) for lot in lots]
  assert len(id_list) == len(set(id_list))

  for lot in lots:
    if lot.adjustment and lot.adjustment != 0:
      if rounded_dollars:
        profit = round(lot.proceeds) - round(lot.basis) + round(lot.adjustment)
      else:
        profit = lot.proceeds - lot.basis + lot.adjustment
      # print "profit", profit, "adj", lot.adjustment
      if merged:
        # If merged data, then can have a greater loss than the adjustment
        assert(profit < .0000001)
      else:
        # Normal split lots, should never have any profit or loss if wash
        assert(abs(profit) < .0000001)

def print_lots(lots, merged=False, rounded_dollars=False):
  mods = " (merged split-lots)" if merged else ""
  mods += " (safe for whole-dollar arithmetic)" if rounded_dollars else ""
  print "Printing %d lots%s:" % (len(lots), mods)

  # Validate data
  assert_lots_values(lots, merged, rounded_dollars)

  # Output summary counters
  basis = 0
  proceeds = 0
  days = 0
  adjustment = 0
  count = 0
  # go through all lots
  for lot in lots:

    print lot

    count += lot.count
    basis += lot.basis
    if lot.proceeds:
      proceeds += lot.proceeds
    if lot.adjustment:
      adjustment += lot.adjustment

  print "Totals: Count %d Basis %.3f Proceeds %.3f Adj: %.3f (basis-adj: %.3f)"\
      % (count, basis, proceeds, adjustment, basis - adjustment)
