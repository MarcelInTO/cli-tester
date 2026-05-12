# A wct test that should always pass. Used as input to meta-tests.
from wct import checkPathNotExists

checkPathNotExists("nothing_here.txt")
