#include "hive/Ruleset.h"

Ruleset Ruleset::legacyExpanded()
{
    return Ruleset{"legacy-expanded", {1, 2, 2, 3, 3, 1, 1, 1}, false, 4, true, 0};
}

Ruleset Ruleset::baseHivePaper()
{
    return Ruleset{"base-hive-paper-profile", {1, 2, 2, 3, 3, 0, 0, 0}, true, 4, true, 3};
}
