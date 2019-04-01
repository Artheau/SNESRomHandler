#Originally written by Artheau
#In April 2019 while observing the subtle scent of cleaning chemicals
#
#This file defines a class that contains all the functions necessary to do the expected operations to an SNES ROM
#e.g. read/write/etc.
#Note: it abstracts away little endian notation.  Just write into memory in big endian, and read out in big endian.

import struct
import os
import enum

#enumeration for the rom types
class RomType(enum.Enum):
    #using the least significant bits of the internal header here
    # for consistency
    LOROM   = 0b000
    HIROM   = 0b001
    EXLOROM = 0b010
    EXHIROM = 0b101

class RomHandler:
    def __init__(self, filename):
        #figure out if it has a header by inferring from the overall file size
        self._HEADER_SIZE = 0x200
        file_size = os.path.getsize(filename)
        if file_size % 0x8000 == 0:
            self._rom_is_headered = False
            self._rom_size = file_size
        elif file_size % 0x8000 == self._HEADER_SIZE:
            self._rom_is_headered = True
            self._rom_size = file_size - self._HEADER_SIZE
        else:
            raise AssertionError(f"{filename} does not contain an even number of half banks...is this a valid ROM?")

        #open the file and store the contents
        with open(filename, "rb") as file:
            if self._rom_is_headered:
                self._header = bytearray(file.read(self._HEADER_SIZE))
            self._contents = bytearray(file.read())
            
        #Determine the type of ROM (e.g. LoRom or HiRom)
        LOROM_CHECKSUM_OFFSET = 0x7FDE
        HIROM_CHECKSUM_OFFSET = 0xFFDE
        #by comparing against checksum complement
        if self.read(LOROM_CHECKSUM_OFFSET, 2) + self.read(LOROM_CHECKSUM_OFFSET-2, 2) == 0xFFFF:
            self._type = RomType.LOROM
        elif self.read(HIROM_CHECKSUM_OFFSET, 2) + self.read(HIROM_CHECKSUM_OFFSET-2, 2) == 0xFFFF:
            self._type = RomType.HIROM
        else:   #the checksum is bad, so try to infer from the internal header being valid characters or not 
            LOWER_ASCII = 0x20
            UPPER_ASCII = 0x7E
            ROM_TITLE_SIZE = 21
            lorom_char_count = sum(x >= LOWER_ASCII and x <= UPPER_ASCII for x in self.read(0x7FC0, "1"*ROM_TITLE_SIZE))
            hirom_char_count = sum(x >= LOWER_ASCII and x <= UPPER_ASCII for x in self.read(0xFFC0, "1"*ROM_TITLE_SIZE))
            if lorom_char_count >= hirom_char_count:
                self._type = RomType.LOROM
            else:
                self._type = RomType.HIROM

        #check to make sure the makeup byte confirms our determination of the ROM type, also check for ExHiRom and friends
        makeup_byte = self._read_from_internal_header(0x15, 1)
        if self._type == RomType.LOROM:
            if makeup_byte not in [0x20,0x30]:   #0x20 and 0x30 are lorom
                if makeup_byte == 0x32:
                    self._type = RomType.EXLOROM
                elif makeup_byte == 0x23:
                    pass   #Maybe SA-1 will work with this library.  MAYBE.
                else:
                    raise AssertionError(f"Cannot recognize the makeup byte of this ROM: {hex(makeup_byte)}.")

        elif self._type == RomType.HIROM:
            if makeup_byte not in [0x21, 0x31]:   #0x21 and 0x31 are hirom
                if makeup_byte == 0x35:
                    self._type = RomType.EXHIROM
                elif makeup_byte == 0x23:
                    pass   #Maybe SA-1 will work with this library.  MAYBE.  Maybe.  maybe.  Emphasis on "maybe".
                else:
                    raise AssertionError(f"Cannot recognize the makeup byte of this ROM: {hex(makeup_byte)}.")

        #information about onboard RAM/SRAM and enhancement chips lives here
        #rom_type_byte = self._read_from_internal_header(0x16, 1)
        
        #can also retrieve SRAM size if desired
        #self._SRAM_size = 0x400 << self._read_from_internal_header(0x18,1)


    def save(self, filename, overwrite=False):
        #check to see if a file by this name already exists
        if not overwrite and os.path.isfile(filename):
            raise FileExistsError(f"{filename} already exists")
        with open(filename, "wb") as file:
            if self._rom_is_headered:
                file.write(self._header)
            file.write(self._contents)


    def read(self,addr,encoding):
        #expects a ROM address and an encoding
        #
        #if encoding is an integer:
        #returns a single value which is the unpacked integer in normal (big-endian) format from addr to addr+encoding
        #example: .read(0x7FDC, 2) will return the big-endian conversion of bytes 0x7FDC and 0x7FDD
        #
        #if encoding is a string:
        #starting from addr, starts unpacking values according to the encoding string,
        # converting them from little endian as it goes
        #example: .read(0x7FDC, "22") will read two words that start at 0x7FDC and return them in normal (big-endian) format as a list

        if type(encoding) is int:
            return self._read_single(addr,encoding)
        elif type(encoding) is str:
            returnvalue = []
            for code in encoding:
                size = int(code)
                returnvalue.append(self._read_single(addr, size))
                addr += size
            return returnvalue
        else:
            raise AssertionError(f"received call to read() but the encoding was not recognized: {encoding}")

    def write(self,addr,values,encoding):
        #if encoding is an integer:
        #expects a value and an address to write to.  It will convert it to little-endian format automatically.
        #example: .write(0x7FDC, 0x1f2f, 2) will write 0x2f to 0x7FDC and 0x1f to 0x7FDD
        #
        #if encoding is a string:
        #does essentially the same thing, but expects a list of values instead of a single value
        # converting them to little endian and writing them in order.
        #example: .write(0x7FDC, [0x111f,0x222f], "22") will write $1f $11 $2f $22 to 0x7FDC-0x7FDF

        if type(encoding) is int:
            if type(values) is int:
                self._write_single(values,addr,encoding)
            else:
                raise AssertionError(f"received call to write() a single value, but {values} was not a single value")
        elif type(encoding) is str:
            if type(values) is int:
                raise AssertionError(f"received call to do multiple writes, but only one value was given.  Should encoding be an integer instead of a string?")
            if len(values) != len(encoding):
                raise AssertionError(f"received call to write() but length of values and encoding did not match: i.e. {len(values)} vs. {len(encoding)}")
            for value,code in zip(values,encoding):
                size = int(code)
                self._write_single(value, addr, size)
                addr += size
        else:
            raise AssertionError(f"received call to write() but the encoding was not recognized: {encoding}")

    def read_from_snes_address(self,addr,encoding):
        return self.read(self.convert_to_pc_address(addr),encoding)

    def write_to_snes_address(self,addr,values,encoding):
        return self.write(self.convert_to_pc_address(addr),values,encoding)      

    def convert_to_snes_address(self, addr):
        #takes as input a PC ROM address and converts it into the address space of the SNES
        if addr > self._rom_size or addr < 0:
            raise AssertionError(f"Function convert_to_snes_address() called on {hex(addr)}, but this is outside the ROM file.")
        
        if self._type == RomType.LOROM:
            bank = addr // 0x8000
            offset = addr % 0x8000
            snes_address = (bank+0x80)*0x10000 + (offset+0x8000)

        elif self._type == RomType.HIROM:
            snes_address = addr + 0x800000   #hirom is so convenient in this way

        elif self._type == RomType.EXLOROM:
            bank = addr // 0x8000
            offset = addr % 0x8000
            if bank < 0x40:
                snes_address = (bank+0x80)*0x10000 + (offset+0x8000)
            elif bank < 0x7F:
                snes_address = (bank-0x80)*0x10000 + (offset+0x8000)
            else:
                raise AssertionError(f"Function convert_to_snes_address() called on address {hex(addr)}, but this part of ROM is not mapped in ExLoRom.")
                
        elif self._type == RomType.EXHIROM:
            if addr < 0x400000:
                snes_address = addr + 0xC00000
            elif addr < 0x7E0000:
                snes_address = addr
            elif addr % 0x10000 > 0x8000:   #only the upper banks of this last little bit are mapped
                snes_address = addr - 0x400000    #for instance, 0x7E8000 PC is mapped to 0x3E8000 SNES
            else:
                raise AssertionError(f"Function convert_to_snes_address() called on {hex(addr)}, but this part of ROM is not mapped in ExHiRom.")

        else:
            raise NotImplementedError(f"Function convert_to_snes_address() called with not implemented type {self._type}")

        return snes_address
    
        
    def convert_to_pc_address(self, addr):
        #takes as input an address in the SNES address space and maps it to the correct address in the PC ROM.
        if addr > 0xFFFFFF or addr < 0:
            raise AssertionError(f"Function convert_to_pc_address() called on {hex(addr)}, but this is outside SNES address space.")
        
        bank = addr // 0x10000
        offset = addr % 0x10000

        if self._type == RomType.LOROM:
            #This particular part of address space has something to do with MAD-1 or lack thereof
            if bank >= 0x40 and bank < 0x70 and offset < 0x8000:
                offset += 0x8000
            #Now check for the usual stuff
            if offset < 0x8000 or bank in [0x7E,0x7F]:
                raise AssertionError(f"Function convert_to_pc_address() called on {hex(addr)}, but this does not map to ROM.")
            else:
                pc_address = (bank % 0x80)*0x8000 + (offset - 0x8000)
                    
        elif self._type == RomType.HIROM:
            if bank in [0x7E, 0x7F] or (bank < 0xC0 and offset < 0x8000):
                raise AssertionError(f"Function convert_to_pc_address() called on {hex(addr)}, but this does not map to ROM.")
            else:
                pc_address = (bank // 0x40)*0x10000 + offset

        elif self._type == RomType.EXLOROM:
            #This particular part of address space has something to do with MAD-1 or lack thereof
            if bank >= 0x40 and bank < 0x70 and offset < 0x8000:
                offset += 0x8000
            #Now check for the usual stuff
            if bank >= 0x80 and offset >= 0x8000:  #fastrom block
                pc_address = (bank-0x80)*0x8000 + (offset-0x8000)
            elif bank not in [0x7E, 0x7F] and offset >= 0x8000:    #slowrom block
                pc_address = (bank+0x80)*0x8000 + (offset-0x8000)
            else:
                raise AssertionError(f"Function convert_to_pc_address() called on address {hex(addr)}, but this does not map to ROM.")
        
        elif self._type == RomType.EXHIROM:
            if bank >= 0xC0:              #the fastrom block
                pc_address = (bank - 0xC0)*0x10000 + offset
            elif bank >= 0x40 and bank < 0x7E:    #the slowrom block
                pc_address = bank*0x10000 + offset
            elif bank in [0x3E, 0x3F] and offset > 0x8000:    #the little bit of extra room at the end of the slowrom block
                pc_address = (bank + 0x40)*0x10000 + offset
            elif bank >= 0x80 and bank < 0xC0 and offset >= 0x8000:   #the fastrom mirror
                pc_address = (bank - 0x80)*0x10000 + offset
            elif bank < 0x3E and offset >= 0x8000:  #the slowrom mirror
                pc_address = (bank + 0x40)*0x10000 + offset
            else:
                raise AssertionError(f"Function convert_to_pc_address() called on {hex(addr)}, but this does not map to ROM.")
        else:
            raise NotImplementedError(f"Function convert_to_pc_address() called with not implemented type {self._type}")

        if pc_address > self._rom_size:
            raise AssertionError(f"Function convert_to_pc_address() called on {hex(addr)}, and this maps to {hex(pc_address)}, but the ROM is only {hex(self._rom_size)} bytes large.")
        return pc_address


    def equivalent_addresses(self, addr1, addr2):
        #see if two addresses map to the same point in PC ROM
        return self.convert_to_pc_address(addr1) == self.convert_to_pc_address(addr2)


    def expand(self,size):
        #expands the ROM upwards in size to the specified number of MBits.
        #In this implementation, does not work to expand ROMs any higher than 32 MBits.
        if size < 4 or size > 32 or size % 4 != 0:
            raise NotImplementedError(f"Not Implemented to expand ROM to {size} MBits.  Must be a multiple of 4 between 4 and 32.")
        current_size = self._rom_size/0x20000
        if size <= current_size:
            raise AssertionError(f"Received request to expand() to size {size} MBits, but the ROM is already {self._rom_size/0x20000} MBits")

        size_code = 0x07 + (size-1).bit_length()   #this is a code for the internal header which specifies the approximate ROM size.
        self._write_to_internal_header(0x17, size_code, 1)

        pad_byte_amount = size*0x20000-self._rom_size
        self._contents.extend([0]*pad_byte_amount)  #actually extend the ROM by padding with zeros


    def type(self):
    	#to see if the rom is lorom, hirom, etc.
    	return self._type.name


    def add_header(self):
    	self._rom_is_headered = True
    	self._header = bytearray([0]*self._HEADER_SIZE)


    def remove_header(self):
    	self._rom_is_headered = False


    def _read_single(self, addr, size):
        extracted_bytes = self._contents[addr:addr+size]

        if size == 1:
            unpack_code = 'B'
        elif size == 2:
            unpack_code = 'H'
        elif size == 3:
            unpack_code = 'L'
            extracted_bytes.append(b'\x00')    #no native 3-byte unpacking format in Python; this is a workaround to pad the 4th byte
        elif size == 4:
            unpack_code = 'L'
        else:
            raise NotImplementedError(f"_read_single() called to read size {size}, but this is not implemented.")

        return struct.unpack('<'+unpack_code,extracted_bytes)[0]           #the '<' forces it to read as little-endian


    def _write_single(self, value, addr, size):
        if size == 1:
            pack_code = 'B'
        elif size == 2:
            pack_code = 'H'
        elif size == 3:
            pack_code = 'L'
        elif size == 4:
            pack_code = 'L'
        else:
            raise NotImplementedError(f"_write_single() called to write size {size}, but this is not implemented.")

        self._contents[addr:addr+size] = struct.pack('<'+pack_code,value)[0:size]  #the '<' forces it to write as little-endian


    def _read_from_internal_header(self, offset, size):
        if self._type == RomType.LOROM or self._type == RomType.EXLOROM:
            return self.read(offset+0x7FC0,size)
        elif self._type == RomType.HIROM or self._type == RomType.EXHIROM:
            return self.read(offset+0xFFC0,size)
        else:
            raise AssertionError(f"_read_from_internal_header() called with unknown rom type")


    def _write_to_internal_header(self, offset, value, size):
        if self._type == RomType.LOROM or self._type == RomType.EXLOROM:
            return self.write(offset+0x7FC0,value,size)
        elif self._type == RomType.HIROM or self._type == RomType.EXHIROM:
            return self.write(offset+0xFFC0,value,size)
        else:
            raise AssertionError(f"_write_to_internal_header() called with unknown rom type")

        
def main():
	print(f"Called main() on utility library {__file__}")


if __name__ == "__main__":
    main()
