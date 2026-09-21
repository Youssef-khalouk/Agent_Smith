def test():
    with open("/home/reda/Desktop/test.txt") as fd:
        text = fd.read()
        print("Can access")
        print("Hello. From mcp client !")

def main():
    test()

if __name__ == "__main__":
    main()