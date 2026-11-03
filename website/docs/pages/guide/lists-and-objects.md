# Lists and objects

## Lists

```mcn
var scores = [72, 88, 95]
log(scores[0])            // 72 — positions start at 0
log(len(scores))          // 3
scores[1] = 90            // change an item
push(scores, 64)          // add to the end
log(scores[10])           // null — past the end
```

Common operations:

```mcn
var nums = [5, 3, 8, 1]
log(sum(nums))
log(avg(nums))
log(sort(nums))                         // [1, 3, 5, 8]
log(reverse(nums))
log(unique([1, 1, 2]))                  // [1, 2]
log(slice(nums, 1, 3))                  // [3, 8]
log(map(nums, n => n * 10))
log(filter(nums, n => n > 2))
log(reduce(nums, (a, b) => a + b, 0))
log([1, 2] + [3])                       // [1, 2, 3]
```

## Objects

Objects hold named values. Keys don't need quotes.

```mcn
var user = {name: "Ada", role: "admin", tags: ["math"]}
log(user.name)            // Ada
log(user["role"])         // admin
user.email = "ada@example.com"
user.tags[0] = "maths"
log(keys(user))
log(has_key(user, "email"))
log(user.phone)           // null — missing keys read as null
```

Useful functions:

```mcn
var a = {name: "Ada", city: "London", age: 36}
log(pick(a, ["name", "city"]))
log(omit(a, ["age"]))
log(merge(a, {age: 37}))                // later keys win
log(to_json(a))                         // JSON text
log(json_parse("{\"ok\": true}"))
```

## Lists of objects

Database queries return lists of objects, so these come up constantly:

```mcn
var people = [
    {name: "Ada", team: "eng", score: 91},
    {name: "Bo",  team: "ops", score: 78},
    {name: "Cy",  team: "eng", score: 85}
]
var eng = filter(people, p => p.team == "eng")
var names = map(people, p => p.name)
var best = sort(people, "score")[2]
var by_team = group_by(people, "team")
var bo = find(people, p => p.name == "Bo")
log(names)
log(by_team.eng)
```

See the [built-in reference](#/reference/builtins) for every list and object function.
