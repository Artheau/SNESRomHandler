#a collection of functions that are commonly needed for SNES files
from PIL import Image
import numpy as np

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

def image_from_raw_data(tilemaps, DMA_writes):
    #expects:
    #  a list of tilemaps in the 5 byte format: essentially [X position, size+Xmsb, Y, index, palette]
    #  a dictionary consisting of writes to the DMA and what should be there

    canvas = {}

    for tilemap in tilemaps:
        #tilemap[0] and the 0th bit of tilemap[1] encode the X offset
        x_offset = tilemap[0] - (0x100 if get_bit(tilemap[1],0) else 0)

        #tilemap[1] also contains information about whether the tile is 8x8 or 16x16
        big_tile = (tilemap[1] & 0xC2 == 0xC2)

        #tilemap[2] contains the Y offset
        y_offset = (tilemap[2] & 0x7F) - (0x80 if get_bit(tilemap[2],7) else 0)

        #tilemap[3] contains the index of which tile to grab (or tiles in the case of a 16x16)
        index = tilemap[3]

        #tilemap[4] contains palette info, priority info, and flip info
        v_flip = get_bit(tilemap[4], 7) == 1
        h_flip = get_bit(tilemap[4], 6) == 1
        priority = get_bit(tilemap[4], 5) == 1              #TODO: implement a priority system
        palette_offset = (tilemap[4] << 2) & 0b1110000      #this is shifted over so that it can be added to the index value to make a (less than) 8-bit value for "P" mode

        def draw_tile_to_canvas(new_x_offset, new_y_offset, new_index):
            tile_to_write = convert_tile_from_bitplanes(DMA_writes[new_index])
            if h_flip:
               tile_to_write = np.flipud(tile_to_write)
            if v_flip:
               tile_to_write = np.fliplr(tile_to_write)
            for (i,j), value in np.ndenumerate(tile_to_write):
                if value != 0:   #if not transparent
                    canvas[(new_x_offset+i,new_y_offset+j)] = int(palette_offset + value)

        if big_tile:   #draw all four 8x8 tiles
            draw_tile_to_canvas(x_offset+(8 if h_flip else 0),y_offset+(8 if v_flip else 0),index       )
            draw_tile_to_canvas(x_offset+(0 if h_flip else 8),y_offset+(8 if v_flip else 0),index + 0x01)
            draw_tile_to_canvas(x_offset+(8 if h_flip else 0),y_offset+(0 if v_flip else 8),index + 0x10)
            draw_tile_to_canvas(x_offset+(0 if h_flip else 8),y_offset+(0 if v_flip else 8),index + 0x11)
        else:
            draw_tile_to_canvas(x_offset,y_offset,index)

    return to_image(canvas)





def to_image(canvas, zoom=1):

    if canvas.keys():
        x_min = min([x for (x,y) in canvas.keys()])
        x_max = max([x for (x,y) in canvas.keys()])
        y_min = min([y for (x,y) in canvas.keys()])
        y_max = max([y for (x,y) in canvas.keys()])

        x_min = min(0,x_min)
        x_max = max(0,x_max)
        y_min = min(0,y_min)
        y_max = max(0,y_max)

        width = x_max-x_min+1
        height = y_max-y_min+1
        origin = (-x_min,-y_min)

        image = Image.new("P", (width, height), 0)

        pixels = image.load()

        #these next few lines add pink axis lines in case you're into that
        # for i in range(x_min,x_max+1):
        #     pixels[i+origin[0],origin[1]] = (0xFF,0x80,0xFF)    
        # for j in range(y_min,y_max+1):
        #     pixels[origin[0],j+origin[1]] = (0xFF,0x80,0xFF)

        for (i,j),value in canvas.items():
            pixels[i+origin[0],j+origin[1]] = value

        #scale
        if zoom != 1:
            image = image.resize((zoom*(width), zoom*(height)), Image.NEAREST)
            origin = tuple([int(xi*zoom) for xi in origin])
    else:                #the canvas is empty
        image = None
        origin = (0,0)

    return image, origin

def apply_palette(image, palette):
    flat_palette = [x for color in convert_to_rgb(palette) for x in color]
    image.putpalette(flat_palette)                                          #apply palette
    image.putalpha(image.convert('L').point(lambda x: 0 if x==0 else 255, '1'))        #make background transparent
    return image
            

def convert_tile_from_bitplanes(raw_tile):
    #an attempt to make this ugly process mildly efficient
    tile = np.zeros((8,8), dtype=np.uint8)

    tile[:,4] = raw_tile[31:15:-2]
    tile[:,5] = raw_tile[30:14:-2]
    tile[:,6] = raw_tile[15::-2]
    tile[:,7] = raw_tile[14::-2]

    shaped_tile = tile.reshape(8,8,1)

    tile_bits = np.unpackbits(shaped_tile, axis=2)
    fixed_bits = np.packbits(tile_bits, axis=1)
    return np.fliplr(fixed_bits.reshape(8,8).swapaxes(0,-1))
    
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
