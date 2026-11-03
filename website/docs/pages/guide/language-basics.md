# Language basics

MCN is designed to read like a description of what the program does. Blocks are marked by indentation, there are no semicolons or braces, and comments start with `//`.

## Variables

```mcn
var name = "Ada"
var age = 36
var active = true
var nothing = null

age = age + 1      // reassign without `var`
age += 1           // also -=, *=, /=, %=
```

`var` declares a variable; plain `name = value` changes one that already exists.

## Text

```mcn
var first = "Ada"
var last = "Lovelace"
log("Hello, " + first)             // join with +
log("Hello, {first} {last}")       // or put names in {braces}
log("Age: " + str(36))             // numbers join with text automatically too

var poem = """Several lines
of text"""
log(upper(first))
log(len(last))
```

Text in `{braces}` is replaced by the variable of that name. Use `"""triple quotes"""` for text over several lines.

## Numbers and operators

| Kind | Operators |
|---|---|
| Arithmetic | `+ - * / %` |
| Comparison | `== != < > <= >=` |
| Logic | `and or not` |

```mcn
var price = 19.99
var qty = 3
var total = price * qty
log(round(total, 2))
log(total > 50 and qty < 10)
```

`/` always gives a decimal (`7 / 2` is `3.5`). `and`/`or` return one of their values, so `name or "guest"` gives a fallback.

## Decisions

```mcn
var score = 72

if score >= 90
    log("A")
else if score >= 70
    log("C or better")
else
    log("Keep practising")

var result = "pass" if score >= 50 else "fail"     // one-line form
var grade = score >= 90 ? "A" : "B"                 // also works
```

## Loops

```mcn
var fruits = ["apple", "pear", "fig"]

for fruit in fruits
    log(fruit)

for i, fruit in fruits          // with the position
    log(str(i) + ": " + fruit)

for n in range(3)               // 0, 1, 2
    log(n)

var count = 0
while count < 5
    count += 1
    if count == 2
        continue                // skip to the next round
    if count == 4
        break                   // leave the loop
```

## Indentation

Lines inside `if`, `for`, `while`, `function`, `service` and the other blocks are indented by **4 spaces**. The block ends when the indentation goes back.

> **Tip** If MCN says `Expected an indented block after 'if'`, indent the lines under it. If it says a line `doesn't match any enclosing block`, line it up with the block above. Don't mix tabs and spaces.

## Null and missing values

`null` means "no value". Reading a key an object doesn't have gives `null`, and `?.` reads a property only when the object isn't null:

```mcn
var user = {name: "Ada"}
log(user.email)            // null: the key doesn't exist
var nobody = null
log(nobody?.name)          // null instead of an error
log(user.email or "no email")
```

Comparing or doing arithmetic with `null` is an error that says which side is null.
