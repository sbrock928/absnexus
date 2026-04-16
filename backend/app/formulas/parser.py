"""Recursive descent parser — builds AST from tokens."""
from dataclasses import dataclass, field
from app.formulas.tokenizer import Token, TokenType


@dataclass
class NumberNode:
    value: str


@dataclass
class VariableNode:
    name: str


@dataclass
class BinaryOpNode:
    op: str
    left: "ASTNode"
    right: "ASTNode"


@dataclass
class ComparisonNode:
    op: str
    left: "ASTNode"
    right: "ASTNode"


@dataclass
class FunctionCallNode:
    name: str
    args: list["ASTNode"] = field(default_factory=list)


@dataclass
class UnaryMinusNode:
    operand: "ASTNode"


ASTNode = NumberNode | VariableNode | BinaryOpNode | ComparisonNode | FunctionCallNode | UnaryMinusNode


class Parser:
    """Recursive descent parser with standard operator precedence."""

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token | None:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def consume(self) -> Token:
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def expect(self, ttype: TokenType) -> Token:
        t = self.consume()
        if t.type != ttype:
            raise ValueError(f"Expected {ttype}, got {t.type} ({t.value})")
        return t

    def parse(self) -> ASTNode:
        node = self.parse_comparison()
        if self.pos < len(self.tokens):
            raise ValueError(f"Unexpected token: {self.tokens[self.pos]}")
        return node

    def parse_comparison(self) -> ASTNode:
        left = self.parse_expr()
        t = self.peek()
        if t and t.type == TokenType.COMPARISON:
            op = self.consume().value
            right = self.parse_expr()
            return ComparisonNode(op, left, right)
        return left

    def parse_expr(self) -> ASTNode:
        left = self.parse_term()
        while True:
            t = self.peek()
            if t and t.type == TokenType.OPERATOR and t.value in ("+", "-"):
                op = self.consume().value
                right = self.parse_term()
                left = BinaryOpNode(op, left, right)
            else:
                break
        return left

    def parse_term(self) -> ASTNode:
        left = self.parse_unary()
        while True:
            t = self.peek()
            if t and t.type == TokenType.OPERATOR and t.value in ("*", "/"):
                op = self.consume().value
                right = self.parse_unary()
                left = BinaryOpNode(op, left, right)
            else:
                break
        return left

    def parse_unary(self) -> ASTNode:
        t = self.peek()
        if t and t.type == TokenType.OPERATOR and t.value == "-":
            self.consume()
            operand = self.parse_primary()
            return UnaryMinusNode(operand)
        return self.parse_primary()

    def parse_primary(self) -> ASTNode:
        t = self.peek()
        if not t:
            raise ValueError("Unexpected end of expression")

        if t.type == TokenType.NUMBER:
            return NumberNode(self.consume().value)

        if t.type == TokenType.VARIABLE:
            return VariableNode(self.consume().value)

        if t.type == TokenType.FUNCTION:
            return self.parse_function()

        if t.type == TokenType.LPAREN:
            self.consume()
            node = self.parse_comparison()
            self.expect(TokenType.RPAREN)
            return node

        raise ValueError(f"Unexpected token: {t}")

    def parse_function(self) -> FunctionCallNode:
        name = self.consume().value
        self.expect(TokenType.LPAREN)
        args: list[ASTNode] = []
        if self.peek() and self.peek().type != TokenType.RPAREN:
            args.append(self.parse_comparison())
            while self.peek() and self.peek().type == TokenType.COMMA:
                self.consume()
                args.append(self.parse_comparison())
        self.expect(TokenType.RPAREN)
        return FunctionCallNode(name, args)


def parse(tokens: list[Token]) -> ASTNode:
    return Parser(tokens).parse()
