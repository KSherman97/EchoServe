rules = {3: "Fizz", 5: "Buzz", 7: "Bazz"}

for i in range(1, 101):
    output = ""

    for num, word in rules.items():
        if i % num == 0:
            output += word

    print(output or i)