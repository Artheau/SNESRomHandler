#a collection of functions that are commonly needed for SNES files

def get_bit(byteval,idx):
    #https://stackoverflow.com/questions/2591483/getting-a-specific-bit-value-in-a-byte-string
    return ((byteval&(1<<idx))!=0)

def convert_byte_to_signed_int(byte):
    if byte > 255:
        raise AssertionError(f"Function convert_byte_to_signed_int() called on non-byte value {byte}")
    elif byte > 127:
        return (256-byte) * (-1)
    else:
        return byte

def convert_to_rgb(palette):   #expects big endian 2-byte colors in a list
    return [single_convert_to_rgb(color) for color in palette]

def single_convert_to_rgb(color):    #from 555
    red = 8*(color & 0b11111)
    green = 8*((color >> 5) & 0b11111)
    blue = 8*((color >> 10) & 0b11111)
    return (red,green,blue)

def pretty_hex(x,digits=2):                 #displays a hex number with a specified number of digits
    return '0x' + hex(x)[2:].zfill(digits)

def main():
    print(f"Called main() on utility library {__file__}")

if __name__ == "__main__":
    main()
