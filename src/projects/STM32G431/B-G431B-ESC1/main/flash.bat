openocd -f ./openocd.cfg -c "program ./build/main.hex preverify verify reset exit"
