# Lives one level deeper so meta-tests can verify '**' recursive globbing
# finds it.
from wct import passTest

passTest("found me at depth 1")
