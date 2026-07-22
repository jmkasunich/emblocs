/***************************************************************
 * 
 * critreg.h - critical region handling
 * 
 *
 * This module defines a pair of macros that can be used to
 * surround critical regions.
 *
 */

#ifndef CRITREG_H
#define CRITREG_H


#if defined(__ARM_ARCH_PROFILE) && (__ARM_ARCH_PROFILE == 'M')

    #include <stdint.h>
    #include <cmsis_compiler.h>

    #define CRITICAL_ENTER()                    \
        {                                       \
            uint32_t _irq = __get_PRIMASK();    \
            __disable_irq();

    #define CRITICAL_EXIT()                     \
            __set_PRIMASK(_irq);                \
        }

#else

    #define CRITICAL_ENTER()  {

    #define CRITICAL_EXIT()   }

#endif // architecture detection

#endif // CRITREG_H

