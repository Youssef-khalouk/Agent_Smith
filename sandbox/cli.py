import fire

def greeting(name):
    print(f"Hello: {name}")

with open("test.txt", "r") as fd:
    code = file.read()
    print(code)

def main():
    fire.Fire({
        "greeting": greeting
    })

if __name__ == "__main__":
    main()