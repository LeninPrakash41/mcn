# Functions and errors

## Functions

```mcn
function greet(name, greeting = "Hello")
    return greeting + ", " + name + "!"

log(greet("Ada"))                      // Hello, Ada!
log(greet("Ada", "Welcome"))           // Welcome, Ada!
log(greet("Ada", greeting = "Hi"))     // named argument
```

- Parameters can have defaults (`greeting = "Hello"`).
- Calling with too many or too few arguments is an error that names the missing parameter.
- Functions can be used before the line that defines them, and can call themselves:

```mcn
function factorial(n)
    if n <= 1
        return 1
    return n * factorial(n - 1)

log(factorial(5))     // 120
```

## Arrow functions

Short functions for `map`, `filter`, `reduce` and `sort`:

```mcn
var prices = [12, 30, 8]
var doubled = map(prices, p => p * 2)
var cheap = filter(prices, p => p < 20)
var total = reduce(prices, (sum, p) => sum + p, 0)
```

## Methods

Any built-in can be called as a method on its first argument, so these pairs are the same:

```mcn
var title = "hello world"
log(upper(title))
log(title.upper())

log(contains(title, "world"))
log(title.contains("world"))

var nums = [3, 1, 2]
log(sum(nums))
log(nums.sum())
```

Your own functions work the same way: `name.shout()` calls `shout(name)`. A misspelt method is an error with a suggestion: `A text value has no method 'contanis'. Did you mean 'contains'?`

## Throwing and catching errors

```mcn
function withdraw(balance, amount)
    if amount > balance
        throw "Not enough money"
    return balance - amount

try
    withdraw(10, 50)
catch e
    log("Failed: " + e.message)     // Failed: Not enough money
finally
    log("done")
```

`e.message` is the error text and `e.line` the line it came from. A bare `catch` (without a name) makes the message available as `error`.

## Reading error messages

When something goes wrong, MCN shows the line, points at the problem and suggests a fix:

```output
Name error on line 4, column 21: Undefined variable 'totl'
   4 | log("Total: " + str(totl))
     |                     ^^^^
Hint: Did you mean 'total'?
```

Run `mcn check file.mcn` to find these without running the program. The [error reference](#/reference/errors) lists the common ones.
