patch
- A `[[silk.art]]` entry without `svg`, or with a key it does not take, is an error of the board file when edakit loads it – entry, key and the keys it takes –, not a KeyError in `silk apply` once it has reached EasyEDA (#338).
