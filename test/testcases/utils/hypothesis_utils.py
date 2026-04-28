
#


import hypothesis.strategies as st


@st.composite
def valid_names(draw):
    base_chars = "abcdefghijklmnopqrstuvwxyz_"
    first_char = draw(st.sampled_from([c for c in base_chars if c.isalpha() or c == "_"]))
    remaining = draw(st.text(alphabet=st.sampled_from(base_chars), min_size=0, max_size=128 - 2))

    name = (first_char + remaining)[:128]
    return name.encode("utf-8").decode("utf-8")
