#include "cmsis_os2.h"
#include "stm32f0xx_hal.h"
#include <stdio.h>

ADC_HandleTypeDef hadc1;
UART_HandleTypeDef huart2;

#define BUFFER_SIZE 8

float voltageBuffer[BUFFER_SIZE] = {0.0f};

osMutexId_t dataMutex;

void AdcTask(void *argument) {
    (void)argument;
    while (1) {

        for (int i = 0; i < BUFFER_SIZE; i++) {

            HAL_ADC_Start(&hadc1);

            HAL_ADC_PollForConversion(&hadc1, HAL_MAX_DELAY);

            uint16_t value = HAL_ADC_GetValue(&hadc1);

            float volts = (3.3f * value) / 4095.0f;

            voltageBuffer[i] = volts;

        }
        osDelay(10);
        
    }
}

void UartTask(void *argument) {
    (void)argument;
    while (1) {
        char msg[160];

        int len = 0;

        for (int i = 0; i < BUFFER_SIZE; i++) {

            len += snprintf(msg + len, (size_t)(sizeof(msg) - len),
                            "%.2f ", voltageBuffer[i]);

        }

        len += snprintf(msg + len, (size_t)(sizeof(msg) - len), "\r\n");

        HAL_UART_Transmit(&huart2, (uint8_t *)msg, len, HAL_MAX_DELAY);

        osDelay(100);

    }
}

void SystemClock_Config(void);
void MX_ADC1_Init(void);
void MX_USART2_UART_Init(void);

int main(void) {
    HAL_Init();
    SystemClock_Config();
    MX_ADC1_Init();
    MX_USART2_UART_Init();

    osKernelInitialize();

    dataMutex = osMutexNew(NULL);

    osThreadNew(AdcTask,  NULL, NULL);
    osThreadNew(UartTask, NULL, NULL);

    osKernelStart();
    while (1) { }
}
