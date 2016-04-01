# Copyright Google

# BSD License

import inspect
import lot
import os
import progress_logger
import wash

TEST_DIR = os.path.join(
  os.path.dirname(inspect.getfile(inspect.currentframe())), 'tests')

def run_test(input_csv, expected_out_csv):
  lots = lot.load_lots(input_csv)
  out = wash.perform_wash(lots, progress_logger.NullLogger())
  expected = lot.load_lots(expected_out_csv)
  out.sort(cmp=wash.cmp_by_buy_date)
  expected.sort(cmp=wash.cmp_by_buy_date)
  # TODO: lot.__eq__ compares all members, including original_form_position
  # so need to rethink how to test things or to use different implementation
  # for merging split options (-m). Using str() for now, instead of the
  # fuller == operation.
  if str(out) != str(expected):
    print "Test failed:", input_csv
    print "Got result:"
    lot.print_lots(out)
    print "\nExpected:"
    lot.print_lots(expected)
  else:
    print "Test passed:", input_csv

def run_test_file(filename):
    run_test(os.path.join(TEST_DIR, filename),
             os.path.join(TEST_DIR, filename.rsplit('.', 1)[0] + "_out.csv"))

def main():
  tests = [name for name in os.listdir(TEST_DIR) \
           if (name.endswith(".csv") and not name.endswith("_out.csv"))]
  for test in tests:
    run_test(os.path.join(TEST_DIR, test),
             os.path.join(TEST_DIR, test.rsplit('.', 1)[0] + "_out.csv"))

if __name__ == "__main__":
  main()

