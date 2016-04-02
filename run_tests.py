# Copyright Google

# BSD License

# The tests/ directory contains input files and _out.csv reference output files
# which should match the wash sale processing of the input files.
# Example commands to create the original reference output:
# python ../wash.py -w {input}.csv -q -o {input}_out.csv
#
# The tests/merged folder contains the tests using the -m merge option:
# python ../wash.py -w {input}.csv -q -m -o merged/{input}_out.csv
#
# The tests/rounded folder contains the tests using the -r round option:
# python ../wash.py -w {input}.csv -q -r -o rounded/{input}_out.csv

import inspect
import lot
import os
import progress_logger
import StringIO
import wash

def run_test(input_csv, expected_out_csv, merge_split_lots=False,
        rounded_dollars=False):
  lots = lot.load_lots(open(input_csv))
  out = wash.perform_wash(lots, progress_logger.NullLogger())
  out.sort(cmp=wash.cmp_by_buy_date)

  # merge split lots back together, if asked.
  if merge_split_lots:
    out = lot.merge_split_lots(out)

  # make the adjustment safe for whole-dollar rounding arithmentic
  if rounded_dollars:
    lot.adjust_for_dollar_rounding(out)

  # Sort both out and expected the same way, so we can compare them.
  out.sort(cmp=wash.cmp_by_buy_date)
  out_csv = StringIO.StringIO()
  lot.save_lots(out, out_csv)

  expected = lot.load_lots(open(expected_out_csv))
  expected.sort(cmp=wash.cmp_by_buy_date)
  expected_csv = StringIO.StringIO()
  lot.save_lots(expected, expected_csv)

  # Report pass/fail
  mods = "(merged split-lots) " if merge_split_lots else ""
  mods += "(safe for whole-dollar arithmetic) " if rounded_dollars else ""
  # lot.__eq__ compares all members, including original_form_position
  # and will also include any future internal data members. So, to compare
  # the test vs expected, we use the output CSV file for both, which should
  # be invariant.
  if out_csv.getvalue() != expected_csv.getvalue():
    print "****\n%sTest failed: %s" % (mods, input_csv)
    print "Got result:"
    print out_csv.getvalue()
    print "\nExpected output:", expected_out_csv
    print expected_csv.getvalue()
  else:
    print "%sTest passed: %s" % (mods, input_csv)

def main():
  test_dir = os.path.join(
    os.path.dirname(inspect.getfile(inspect.currentframe())), 'tests')

  tests = [name for name in os.listdir(test_dir) \
           if (name.endswith(".csv") and not name.endswith("_out.csv"))]
  for test in tests:
    test_path = os.path.join(test_dir, test)
    out_name = test.rsplit('.', 1)[0] + "_out.csv"

    # Basic test, compute wash sale and split lots
    out_path = os.path.join(test_dir, out_name)
    run_test(test_path, out_path)
    
    # Test the merging of split lots
    merged_path = os.path.join(test_dir, 'merged', out_name)
    if os.path.exists(merged_path):
      run_test(test_path, merged_path, merge_split_lots=True)

    # Test the rounded-dollar safety adjustments
    rounded_path = os.path.join(test_dir, 'rounded', out_name)
    if os.path.exists(rounded_path):
      run_test(test_path, rounded_path, rounded_dollars=True)

if __name__ == "__main__":
  main()

