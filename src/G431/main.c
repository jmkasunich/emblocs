#include "stm32g4xx.h"
#include "stm32g4xx_ll_bus.h"
#include "stm32g4xx_ll_pwr.h"
#include "stm32g4xx_ll_rcc.h"
#include "stm32g4xx_ll_system.h"

#include <stdint.h>

#include "main.h"

void SystemClock_Config(void);


// Quick and dirty delay
static void delay (unsigned int time) {
    for (unsigned int i = 0; i < time; i++)
        for (volatile unsigned int j = 0; j < 20000; j++);
}

int main (void) {
    uint32_t reg;
    SystemClock_Config();
    // Turn on the GPIOC peripheral
    RCC->AHB2ENR |= RCC_AHB2ENR_GPIOCEN;
    // Put pin 6 in general purpose output mode
    reg = LED_PORT->MODER;
    reg &= ~(0x03 << 12);
    reg |= 0x01 << 12;
    LED_PORT->MODER = reg;
    // LED_PORT->MODER |= GPIO_MODER_MODER6_0;

    while (1) {
        // Reset the state of pin 6 to output low
        LED_PORT->BSRR = GPIO_BSRR_BR_6;

        delay(500);

        // Set the state of pin 6 to output high
        LED_PORT->BSRR = GPIO_BSRR_BS_6;

        delay(500);
    }

    // Return 0 to satisfy compiler
    return 0;
}


/**
  * @brief  System Clock Configuration
  *         The system Clock is configured as follows :
  *            System Clock source            = PLL (HSE)
  *            SYSCLK(Hz)                     = 170000000
  *            HCLK(Hz)                       = 170000000
  *            AHB Prescaler                  = 1
  *            APB1 Prescaler                 = 1
  *            APB2 Prescaler                 = 1
  *            HSE Frequency(Hz)              = 8000000
  *            PLL_M                          = 2 means PLL input is 4MHz
  *            PLL_N                          = 85 means VCO output is 340MHz
  *            PLL_P                          = 2 means PLLP is 170MHz
  *            PLL_Q                          = 2 means PLLQ is 170MHz
  *            PLL_R                          = 2 means PLLR is 170MHz
  *            Flash Latency(WS)              = 4 wait states
  * @param  None
  * @retval None
  */
void SystemClock_Config(void)
{
  /* Enable voltage range 1 boost mode for frequency above 150 Mhz */
  /* need to enable PWR peripheral clock first */
  LL_APB1_GRP1_EnableClock(LL_APB1_GRP1_PERIPH_PWR);
  LL_PWR_EnableRange1BoostMode();
  LL_APB1_GRP1_DisableClock(LL_APB1_GRP1_PERIPH_PWR);

  /* Set Flash Latency */
  LL_FLASH_SetLatency(LL_FLASH_LATENCY_4);

  /* Running on HSI at reset, HSE must be turned on */
  LL_RCC_HSE_Enable();
  while(LL_RCC_HSE_IsReady() != 1) {};

  /* Main PLL configuration and activation */
  LL_RCC_PLL_ConfigDomain_SYS(LL_RCC_PLLSOURCE_HSE, LL_RCC_PLLM_DIV_2, 85, LL_RCC_PLLR_DIV_2);
  LL_RCC_PLL_Enable();
  while(LL_RCC_PLL_IsReady() != 1) {};

  /* PLL system Output activation */
  LL_RCC_PLL_EnableDomain_SYS();

  /* Sysclk activation on the main PLL */
  /* need to run at half-speed for a bit when final speed is > 80MHz */
  /* set prescaler to 2 temporarily */
  LL_RCC_SetAHBPrescaler(LL_RCC_SYSCLK_DIV_2);
  LL_RCC_SetSysClkSource(LL_RCC_SYS_CLKSOURCE_PLL);
  while(LL_RCC_GetSysClkSource() != LL_RCC_SYS_CLKSOURCE_STATUS_PLL)
  {
  };

  /* Insure 1µs transition state at intermediate medium speed clock based on DWT */
  CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
  DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
  DWT->CYCCNT = 0;
  while(DWT->CYCCNT < 100);

  /* switch to full speed; set AHB prescaler to 1 */
  LL_RCC_SetAHBPrescaler(LL_RCC_SYSCLK_DIV_1);

  /* Set APB1 & APB2 prescaler*/
  LL_RCC_SetAPB1Prescaler(LL_RCC_APB1_DIV_1);
  LL_RCC_SetAPB2Prescaler(LL_RCC_APB2_DIV_1);

  /* Set systick to 1ms in using frequency set to 170MHz */
  /* This frequency can be calculated through LL RCC macro */
  /* ex: __LL_RCC_CALC_PLLCLK_FREQ(HSI_VALUE,
                                  LL_RCC_PLLM_DIV_4, 85, LL_RCC_PLLR_DIV_2) */
  //LL_Init1msTick(170000000);

  /* Update CMSIS variable (which can be updated also through SystemCoreClockUpdate function) */
  //LL_SetSystemCoreClock(170000000);
}