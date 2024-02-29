# Copyright (c) 2024 Steven Loscalzo
# Distributed under the terms of the MIT License.
# SPDX-License-Identifier: MIT
""" Datastructure used to facilitate rapid string matching
from a fixed set of options.

This is a Trie with a few specific options:
* It is case sensitive by default, but can be controlled when querying:
* In addition to substrings, it matches strings after non-alpha characters.

For example:
```python
trie.match("AC")  # would match "Alphabet City" and "ACE".
trie.match("Ac")  # would not match either, but would match "Accelerate"
trie.match("Ac", False)  # would match all three results.
```

"""
from typing import Any, Dict, List, Optional


class TrieNode:
    """ A single node in a Trie data structure.

    Attributes:
        self.letter (str): the character this node matches.
        self.parent (TrieNode): the previous node in the Trie.
        self.children (Dict[str, "TrieNode"]): the immediate subsequent nodes in the Trie.
        self.prefix (str): The substring that leads to this node.
        self.downstream_roots (List["TrieNode"]): tokens that follow this node.
        self.terminal (bool):  True if this is the last letter in an option. Defaults to False.

    """
    def __init__(self, letter: str, parent: Optional["TrieNode"]) -> None:
        self.letter = letter
        self.parent = parent
        self.children: Dict[str, "TrieNode"] = {}
        self.prefix = ""
        self.downstream_roots: List["TrieNode"] = []
        self.terminal = False

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, TrieNode):
            return other.letter == self.letter
        if isinstance(other, str):
            return other == self.letter
        return False

    def __str__(self) -> str:
        return f"{self.prefix}-> {self.letter} -> {self.children.keys()}"

    def __repr__(self) -> str:
        return f"{self.prefix}-> {self.letter} -> {self.children.keys()}"


class Trie:
    """ Trie datastructure that can be dynamically grown.

    """
    MIN_LENGTH = 2  # The smallest length query to allow searches for.

    def __init__(self) -> None:
        self.root = TrieNode("", None)

    def insert(self, word: str) -> None:
        """ Add a new word to this Trie.

        Args:
            word (str): Empty strings and null values cause no change to the structure.
        """
        self._insert(self.root, word, word)

    def _insert(self, node: TrieNode, word: str, full_word: str) -> None:
        if word:
            if word[0] in node.children:
                self._insert(node.children[word[0]], word[1:], full_word)
            else:
                # This can be optimized to store only the suffix in a single node
                children = node.children
                next_root = not node.letter.isalnum()
                for pos, letter in enumerate(word):
                    new_node = TrieNode(letter, node)
                    children[letter] = new_node
                    children = new_node.children
                    if next_root:
                        new_node.prefix = full_word[: -len(word) + pos]
                    next_root = not letter.isalnum()
                    node = new_node
                node.terminal = True  # New node is terminal
                # Fix downstream roots:
                last_roots: List[TrieNode] = []
                while node.parent is not None:
                    node.downstream_roots += last_roots
                    if node.prefix != "":
                        last_roots.append(node)
                    node = node.parent
                node.downstream_roots += last_roots
        else:
            node.terminal = True  # Existing node is terminal

    def match(self, query: str, case_sensitive: bool = True) -> List[str]:
        """ Return all previously inserted words that match the query.

        Only queries at least as long as MIN_LENGTH (Default 2)

        Args:
            query (str): Null queries match nothing.
            case_sensitive (bool, optional): Whether case matters in the match. Defaults to True.

        Returns:
            List[str]: A list of all matches.
        """
        matches: List[str] = []
        if query and len(query) >= self.MIN_LENGTH:
            alt_match = ""
            if not case_sensitive:
                alt_match = "".join([ch.lower() if ch.isupper() else ch.upper() for ch in query])
            self._consecutive_match(self.root, query, self.root.prefix, matches, alt_match)
        return list(set(matches))

    def _consecutive_match(
        self, node: TrieNode, query: str, prefix: str, matches: List[str], case_query: str = ""
    ):
        prefix += node.letter
        if not query:
            if node.terminal:
                matches.append(prefix)
            if node.children:
                for child in node.children.values():
                    self._consecutive_match(child, query, prefix, matches, case_query)
                if case_query:  # Case insesitive match
                    for child in node.children.values():
                        self._consecutive_match(child, case_query, prefix, matches, query)
        else:
            if query[0] in node.children:  # Exact match
                self._consecutive_match(
                    node.children[query[0]], query[1:], prefix, matches
                )
            # Check for skip matches
            for root in node.downstream_roots:
                if root.letter == query[0]:
                    self._consecutive_match(root, query[1:], root.prefix, matches)
            if case_query:  # case insesitive match
                if case_query[0] in node.children:  # Exact match
                    self._consecutive_match(
                        node.children[case_query[0]], case_query[1:], prefix, matches, query[1:]
                    )
                # Check for skip matches
                for root in node.downstream_roots:
                    if root.letter == case_query[0]:
                        self._consecutive_match(
                            root,
                            case_query[1:],
                            root.prefix,
                            matches,
                            query[1:]
                        )
