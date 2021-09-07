from tqdm import tqdm
from hashlib import md5
from pathlib import Path
from src.utils.params import (
    Tokens,
    TokenBasedSpan,
    CharBasedSpan,
    Label,
)
from typing import Dict, List, Tuple
from flashtext import KeywordProcessor
from loguru import logger
from .abstract_model import NERModel
from collections import Counter
import inflection
from .chunker import Chunker, Chunk
from src.utils.utils import UnionFind
import copy
import pickle
import sys
from src.dataset.term2cat.term2cat import Term2Cat


def translate_char_level_to_token_level(
    char_based_spans: List[CharBasedSpan], tokens: Tokens, labels: List[str]
) -> List[TokenBasedSpan]:
    snt = " ".join(tokens)
    cid = 0
    start_cid2tokid = dict()
    end_cid2tokid = dict()
    for tokid, token in enumerate(tokens):
        start_cid2tokid[cid] = tokid
        cid += len(token)
        end_cid2tokid[cid] = tokid + 1
        cid += 1
    token_based_spans = []
    left_char_based_spans = []
    for (s, e), l in zip(char_based_spans, labels):
        if s in start_cid2tokid and e in end_cid2tokid:
            token_based_spans.append(((start_cid2tokid[s], end_cid2tokid[e]), l))
            left_char_based_spans.append(((s, e)))
        elif e in end_cid2tokid:
            nearest_start_cid = max([ws for ws in start_cid2tokid.keys() if ws < s])
            token_based_spans.append(
                ((start_cid2tokid[nearest_start_cid], end_cid2tokid[e]), l)
            )
            left_char_based_spans.append(((nearest_start_cid, e)))
    for (cs, ce), ((ts, te), l) in zip(left_char_based_spans, token_based_spans):
        assert snt[cs:ce] == " ".join(tokens[ts:te])
    return token_based_spans


class ComplexKeywordProcessor:
    def __init__(self, term2cat: Dict[str, str]) -> None:
        buffer_dir = Path("data").joinpath(
            "buffer",
            md5(("ComplexKeywordProcessor from " + str(term2cat)).encode()).hexdigest(),
        )
        if not buffer_dir.exists():
            term2cat = copy.copy(term2cat)  # pythonでは参照渡しが行われるため
            case_sensitive_term2cat = dict()
            # 小文字化した際に2回以上出現するものを見つける。これらをcase sensitiveとする
            duplicated_lower_terms = []
            for term, num in Counter([term.lower() for term in term2cat]).most_common():
                if num >= 2:
                    duplicated_lower_terms.append(term)
                else:
                    break
            for term, cat in term2cat.items():
                if term.upper() == term:
                    # 略語(大文字に変化させても形状が変化しないもの)をcase_sensitive_term2catとする
                    #  & これらを　term2catから取り除く
                    case_sensitive_term2cat[term] = cat
                elif term.lower() in duplicated_lower_terms:
                    case_sensitive_term2cat[term] = cat
            # 残りのものをcase insensitiveとする
            for term in case_sensitive_term2cat:
                del term2cat[term]

            self.reversed_case_sensitive_keyword_processor = KeywordProcessor(
                case_sensitive=True
            )
            self.reversed_case_insensitive_keyword_processor = KeywordProcessor(
                case_sensitive=False
            )
            for term, cat in tqdm(case_sensitive_term2cat.items()):
                self.reversed_case_sensitive_keyword_processor.add_keyword(
                    "".join(reversed(term)), cat
                )
            for term, cat in tqdm(term2cat.items()):
                # case insensitiveのものに関しては複数形を追加する
                pluralized_term = inflection.pluralize(term)
                self.reversed_case_insensitive_keyword_processor.add_keyword(
                    "".join(reversed(term)), cat
                )
                self.reversed_case_insensitive_keyword_processor.add_keyword(
                    "".join(reversed(pluralized_term)), cat
                )
            sys.setrecursionlimit(10000)
            buffer_dir.mkdir()
            with open(
                buffer_dir.joinpath("reversed_case_sensitive_keyword_processor.pkl"),
                "wb",
            ) as f:
                pickle.dump(self.reversed_case_sensitive_keyword_processor, f)
            with open(
                buffer_dir.joinpath("reversed_case_insensitive_keyword_processor.pkl"),
                "wb",
            ) as f:
                pickle.dump(self.reversed_case_insensitive_keyword_processor, f)
        with open(
            buffer_dir.joinpath("reversed_case_sensitive_keyword_processor.pkl"), "rb"
        ) as f:
            self.reversed_case_sensitive_keyword_processor = pickle.load(f)
        with open(
            buffer_dir.joinpath("reversed_case_insensitive_keyword_processor.pkl"), "rb"
        ) as f:
            self.reversed_case_insensitive_keyword_processor = pickle.load(f)

    def extract_keywords(self, sentence: str, **kwargs) -> List:
        reversed_snt = "".join(reversed(sentence))
        reversed_keywords = (
            self.reversed_case_sensitive_keyword_processor.extract_keywords(
                reversed_snt, span_info=True, **kwargs
            )
        )
        reversed_keywords += (
            self.reversed_case_insensitive_keyword_processor.extract_keywords(
                reversed_snt, span_info=True, **kwargs
            )
        )
        keywords = [
            (label, len(sentence) - e, len(sentence) - s)
            for label, s, e in reversed_keywords
        ]
        return list(set(keywords))


def leave_only_longet_match(
    matches: List[Tuple[TokenBasedSpan, Label]]
) -> List[Tuple[TokenBasedSpan, Label]]:
    if matches:
        spans, labels = zip(*matches)
        spans = [set(range(s, e)) for s, e in spans]
        syms = [(i, i) for i in range(len(matches))]
        for i1, s1 in enumerate(spans):
            for i2, s2 in enumerate(spans):
                if i2 > i1:
                    if s1 & s2:
                        syms.append((i1, i2))
        uf = UnionFind()
        for i, j in syms:
            uf.union(i, j)
        duplicated_groups = [g for g in uf.get_groups() if len(g) > 1]
        if duplicated_groups:
            remove_matches = set()
            for dg in duplicated_groups:
                given_matches = sorted(dg)
                ends = [matches[mid][0][1] for mid in given_matches]
                starts = [
                    matches[mid][0][0]
                    for mid in given_matches
                    if matches[mid][0][1] == max(ends)
                ]
                left_start = min(starts)
                left_end = max(ends)
                for max_length_matchid in given_matches:
                    (ms, me), ml = matches[max_length_matchid]
                    if ms == left_start and me == left_end:
                        break
                for mid in dg:
                    if mid != max_length_matchid:
                        remove_matches.add(mid)

            matches = [m for mid, m in enumerate(matches) if mid not in remove_matches]
    return matches


def ends_with_match(
    chunks: List[Chunk], matches: List[Tuple[TokenBasedSpan, Label]]
) -> List[Tuple[TokenBasedSpan, Label]]:
    return_matches = []
    for s, e in chunks:
        end_matches = [((ms, me), l) for (ms, me), l in matches if me == e and s <= ms]
        if end_matches:
            if len(end_matches) == 1:
                return_matches.append(((s, e), end_matches[0][1]))
            else:
                raise NotImplementedError
    return return_matches


def exact_match(
    chunks: List[Chunk], matches: List[Tuple[TokenBasedSpan, Label]]
) -> List[Tuple[TokenBasedSpan, Label]]:
    return_matches = []
    span2label = dict(matches)
    return_matches = [(c, span2label[c]) for c in chunks if c in span2label]
    return return_matches


def right_shift_match(
    chunks: List[Chunk], matches: List[Tuple[TokenBasedSpan, Label]]
) -> List[Tuple[TokenBasedSpan, Label]]:
    return_matches = []
    for cs, ce in chunks:
        for (ms, me), l in matches:
            if cs <= ms and me <= ce:
                return_matches.append(((cs, me), l))
    # return_matches = [(c, span2label[c]) for c in chunks if c in span2label]
    return return_matches


class NERMatcher:
    def __init__(self, term2cat: Dict[str, str]) -> None:
        self.term2cat = term2cat
        dictionary_size = len(self.term2cat)
        logger.info("dictionary size: %d" % len(self.term2cat))
        logger.info(
            "class wise statistics: %s"
            % str(Counter(self.term2cat.values()).most_common())
        )
        keyword_processor = ComplexKeywordProcessor(self.term2cat)
        assert len(self.term2cat) == dictionary_size  # 参照渡しで破壊的挙動をしていないことの保証
        self.keyword_processor = keyword_processor
        # if chunker:
        #     self.chunker = chunker
        # else:
        #     self.chunker = None

    def __call__(
        self,
        tokens: Tokens,
        chunks: List[Chunk] = None,
        chunker_usage: str = "endswith",
    ) -> List[Tuple[TokenBasedSpan, Label]]:
        snt = " ".join(tokens)
        keywords_found = self.keyword_processor.extract_keywords(snt)
        if keywords_found:
            labels, char_based_starts, char_based_ends = zip(*keywords_found)
            spans, labels = map(
                list,
                zip(
                    *leave_only_longet_match(
                        [
                            ((s, e), l)
                            for s, e, l in zip(
                                char_based_starts, char_based_ends, labels
                            )
                        ]
                    )
                ),
            )
            char_based_starts, char_based_ends = map(list, zip(*spans))
            char_based_spans = list(zip(char_based_starts, char_based_ends))
            token_based_matches = translate_char_level_to_token_level(
                char_based_spans, tokens, labels
            )
            matches = leave_only_longet_match(token_based_matches)
            # 文字列重複無くして追加されたのに対処
        else:
            matches = list()
        if chunks:
            # chunks = self.chunker(tokens)
            if chunker_usage == "endswith":
                matches = ends_with_match(chunks, matches)
            elif chunker_usage == "exact":
                matches = exact_match(chunks, matches)
            elif chunker_usage == "right_shift":
                matches = right_shift_match(chunks, matches)
            else:
                raise NotImplementedError
        return leave_only_longet_match(matches)


def joint_adjacent_term(matches):
    syms = [(i, i) for i in range(len(matches))]
    for i1, ((s1, e1), l1) in enumerate(matches):
        for i2, ((s2, e2), l2) in enumerate(matches):
            if i2 > i1:
                if e1 == s2 or e2 == s1:
                    syms.append((i1, i2))
    uf = UnionFind()
    for i, j in syms:
        uf.union(i, j)
    duplicated_groups = [g for g in uf.get_groups() if len(g) > 1]
    if duplicated_groups:
        joint_terms = []
        for dg in duplicated_groups:
            dg = list(dg)
            starts = [matches[mid][0][0] for mid in dg]
            ends = [matches[mid][0][1] for mid in dg]
            (_, _), new_label = matches[dg[ends.index(max(ends))]]
            joint_terms.append(((min(starts), max(ends)), new_label))
        removed_mids = [mid for g in duplicated_groups for mid in g]
        left_matches = [m for mid, m in enumerate(matches) if mid not in removed_mids]
        left_matches += joint_terms
        return left_matches
    else:
        return matches


class NERMatcherModel(NERModel):
    def __init__(
        self,
        chunker_usage: str = "endswith",
        chunker: Chunker = None,
        term2cat: Term2Cat = None,
    ):
        super().__init__()
        self.chunker_usage = chunker_usage
        self.term2cat = term2cat.term2cat
        self.matcher = NERMatcher(term2cat=self.term2cat)
        self.chunker = chunker
        self.args["term2cat"] = self.term2cat
        self.args["chunker_usage"] = chunker_usage
        if chunker:
            self.args["chunker"] = chunker.args
        self.label_names = ["O"] + [
            tag % label
            for label in sorted(set(self.term2cat.values()))
            for tag in {"B-%s", "I-%s"}
        ]

    def predict(self, tokens: List[str], chunks: List[str] = None) -> List[str]:
        if chunks == None and self.chunker:
            chunks = self.chunker.batch_predict([tokens])[0]
        ner_tags = ["O" for tok in tokens]
        matches = joint_adjacent_term(self.matcher(tokens, chunks, self.chunker_usage))
        for (s, e), label in matches:
            for tokid in range(s, e):
                if tokid == s:
                    ner_tags[tokid] = "B-%s" % label
                else:
                    ner_tags[tokid] = "I-%s" % label
        return ner_tags

    def batch_predict(
        self, tokens: List[List[str]], poss: List[List[str]] = None
    ) -> List[List[str]]:
        chunks = None
        if self.chunker:
            chunks = self.chunker.batch_predict(tokens, poss)
        else:
            chunks = [None] * len(tokens)
        return [self.predict(tok, cks) for tok, cks in zip(tokens, chunks)]