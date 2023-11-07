# emblocs
EMbedded BLock Oriented Control System - a modular approach to real-time embedded control

[LinuxCNC](https://github.com/LinuxCNC/linuxcnc) does real-time machine control on a PC, using a modular system referred to as HAL (hardware abstraction layer).

EMBLOCS is an attempt by one of the original HAL developers to provide a similar modular system on lightweight embedded platforms, primarily ARM32.

A major goal is to be compatible with bare-metal programming as well as lightweight real-time operating systems such as [ThreadX](https://github.com/azure-rtos/threadx).  It explicitly is NOT about running on boards like the Raspberry PI that are running a full-blown operating system such as Linux.

The following documents from LinuxCNC describe the existing HAL system far better than I can here:
- [Introduction](http://linuxcnc.org/docs/stable/html/hal/intro.html)
- [Tutorial](http://linuxcnc.org/docs/stable/html/hal/tutorial.html)
- [Basic Concepts](http://linuxcnc.org/docs/stable/html/hal/basic-hal.html)

Some key differences between LinuxCNC's HAL and EMBLOCS:
- Less support for dynamic configuration.  Most EMBLOCS applications will be compiled and loaded into flash memory.
- No files or need for a filesystem.
- Minimal or no use of dynamically allocated memory.
- Components don't have "parameters", only "pins".
- No GUI on the embedded system.  Command line optional on the embedded system.
- Tools like halscope will run on a PC and connect to the embedded system over serial port or other lightweight protocol.

## DISCLAIMER
  
<br>

```
  
Ｔｈｅ ａｕｔｈｏｒｓ ｏｆ ｔｈｉｓ ｓｏｆｔｗａｒｅ ａｃｃｅｐｔ
ａｂｓｏｌｕｔｅｌｙ ｎｏ ｌｉａｂｉｌｉｔｙ ｆｏｒ ａｎｙ
ｈａｒｍ　ｏｒ ｌｏｓｓ ｒｅｓｕｌｔｉｎｇ ｆｒｏｍ ｉｔｓ ｕｓｅ．

Ｉｔ ｉｓ ＥＸＴＲＥＭＥＬＹ ｕｎｗｉｓｅ ｔｏ　ｒｅｌｙ
ｏｎ ｓｏｆｔｗａｒｅ ａｌｏｎｅ ｆｏｒ ｓａｆｅｔｙ．

Any machinery capable of harming persons must have
provisions for completely removing power from all
motors, etc., before persons enter any danger area.

All machinery must be designed to comply with local 
and national safety codes, and the authors of this 
software cannot and do not, take any responsibility 
for such compliance.
  
```

