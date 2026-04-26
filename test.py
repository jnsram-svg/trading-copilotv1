def score_range(cons, bb, retr):
    cons_map = {
        "No": 0,
        "Yes": 1,
        "1T": 1,
        "2T": 2,
        "3T": 3
    }

    bb_map = {
        "No": 0,
        "Yes": 1
    }

    retr_map = {
        "No": 0,
        "0.6": 1,
        "0.78": 2
    }

    # PURE calculation (no +=, no previous state)
    return cons_map[cons] + bb_map[bb] + retr_map[retr]
print(score_range("No", "No", "No"))     # 0
print(score_range("Yes", "No", "No"))    # 1
print(score_range("1T", "No", "No"))     # 1
print(score_range("2T", "No", "No"))     # 2
print(score_range("3T", "No", "No"))     # 3

# reverse
print(score_range("2T", "No", "No"))     # 2
print(score_range("1T", "No", "No"))     # 1
print(score_range("Yes", "No", "No"))    # 1
print(score_range("No", "No", "No"))     # 0