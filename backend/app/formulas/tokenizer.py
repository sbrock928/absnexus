"""Formula tokenizer — breaks formula strings into tokens."""
import re
from dataclasses import dataclass
from enum import Enum


class TokenType(Enum):
    NUMBER = "NUMBER"
    VARIABLE = "VARIABLE"
    FUNCTION = "FUNCTION"
    OPERATOR = "OPERATOR"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    COMMA = "COMMA"
    COMPARISON = "COMPARISON"


@dataclass
class Token:
    type: TokenType
    value: str


FUNCTIONS = {"MIN", "MAX", "ABS", "IF", "ROUND", "CEILING", "FLOOR", "SUM"}

COMPARISON_OPS = {">=", "<=", "!=", "==", ">", "<"}


def tokenize(formula: str) -> list[Token]:
    """Tokenize a formula string into a list of tokens."""
    tokens: list[Token] = []
    i = 0
    s = formula.strip()

    while i < len(s):
        ch = s[i]

        # Whitespace
        if ch in (" ", "\t"):
            i += 1
            continue

        # Comparisons (multi-char first)
        if i + 1 < len(s) and s[i:i+2] in COMPARISON_OPS:
            tokens.append(Token(TokenType.COMPARISON, s[i:i+2]))
            i += 2
            continue
        if ch in (">", "<"):
            tokens.append(Token(TokenType.COMPARISON, ch))
            i += 1
            continue

        # Numbers
        if ch.isdigit() or (ch == "." and i + 1 < len(s) and s[i+1].isdigit()):
            m = re.match(r"\d+\.?\d*", s[i:])
            if m:
                tokens.append(Token(TokenType.NUMBER, m.group()))
                i += m.end()
                continue

        # Negative number after operator/lparen/comma/comparison or at start
        if ch == "-" and i + 1 < len(s) and (s[i+1].isdigit() or s[i+1] == "."):
            if not tokens or tokens[-1].type in (
                TokenType.OPERATOR, TokenType.LPAREN, TokenType.COMMA, TokenType.COMPARISON
            ):
                m = re.match(r"-\d+\.?\d*", s[i:])
                if m:
                    tokens.append(Token(TokenType.NUMBER, m.group()))
                    i += m.end()
                    continue

        # Operators
        if ch in "+-*/":
            tokens.append(Token(TokenType.OPERATOR, ch))
            i += 1
            continue

        # Parens
        if ch == "(":
            tokens.append(Token(TokenType.LPAREN, "("))
            i += 1
            continue
        if ch == ")":
            tokens.append(Token(TokenType.RPAREN, ")"))
            i += 1
            continue

        # Comma
        if ch == ",":
            tokens.append(Token(TokenType.COMMA, ","))
            i += 1
            continue

        # Identifiers: functions or variables
        if ch.isalpha() or ch == "_":
            m = re.match(r"[a-zA-Z_][a-zA-Z0-9_]*", s[i:])
            if m:
                name = m.group()
                if name.upper() in FUNCTIONS:
                    tokens.append(Token(TokenType.FUNCTION, name.upper()))
                else:
                    tokens.append(Token(TokenType.VARIABLE, name))
                i += m.end()
                continue

        raise ValueError(f"Unexpected character \'{ch}\' at position {i} in: {formula}")

    return tokens
