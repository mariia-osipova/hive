CMAKE ?= cmake
PROJECT_ROOT := $(abspath ../..)
BUILD_DIR ?= $(PROJECT_ROOT)/build/cmake

.PHONY: all core hive test test-parte1a test-parte1b test-parte2 test-parte3 \
	test-integracion configure-test configure-core configure-gui clean

all: hive

core: configure-core
	$(CMAKE) --build "$(BUILD_DIR)" --target hive_core

hive: configure-gui
	$(CMAKE) --build "$(BUILD_DIR)" --target hive_gui

test: configure-test
	$(CMAKE) --build "$(BUILD_DIR)" --target hive_tests
	$(CMAKE) --build "$(BUILD_DIR)" --target test

hive_tests: configure-test
	$(CMAKE) --build "$(BUILD_DIR)" --target hive_tests

test-parte1a: hive_tests
	"$(BUILD_DIR)/hive_tests" --gtest_filter='Player.*'

test-parte1b: hive_tests
	"$(BUILD_DIR)/hive_tests" --gtest_filter='QueenMovement.*'

test-parte2: hive_tests
	"$(BUILD_DIR)/hive_tests" --gtest_filter='BeetleMovement.*:GrasshopperMovement.*:Piece.*:StrategyFactory.*-StrategyFactory.CreatesLadybugMovementForLadybug'

test-parte3: hive_tests
	"$(BUILD_DIR)/hive_tests" --gtest_filter='BoardGraphAdapter*:BoardConnectivity.*:BoardCanMove.*:LadybugMovement.*:StrategyFactory.CreatesLadybugMovementForLadybug'

test-integracion: hive_tests
	"$(BUILD_DIR)/hive_tests" --gtest_filter='Game.*:PillbugAbility.*:MosquitoAbility.*:AlphaZeroRules.*'

configure-core:
	$(CMAKE) -S "$(PROJECT_ROOT)" -B "$(BUILD_DIR)" -DHIVE_BUILD_TESTS=OFF -DHIVE_BUILD_GUI=OFF -DHIVE_BUILD_PYTHON=OFF

configure-test:
	$(CMAKE) -S "$(PROJECT_ROOT)" -B "$(BUILD_DIR)" -DHIVE_BUILD_TESTS=ON -DHIVE_BUILD_GUI=OFF -DHIVE_BUILD_PYTHON=OFF

configure-gui:
	$(CMAKE) -S "$(PROJECT_ROOT)" -B "$(BUILD_DIR)" -DHIVE_BUILD_TESTS=OFF -DHIVE_BUILD_GUI=ON -DHIVE_BUILD_PYTHON=OFF

clean:
	rm -rf "$(BUILD_DIR)"
