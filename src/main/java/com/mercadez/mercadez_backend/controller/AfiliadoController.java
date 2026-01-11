package com.mercadez.mercadez_backend.controller;

import com.mercadez.mercadez_backend.entity.Afiliado;
import com.mercadez.mercadez_backend.repository.AfiliadoRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.Optional;

@RestController
@RequestMapping("/afiliados")
@CrossOrigin(origins = "*")
public class AfiliadoController {

    @Autowired
    private AfiliadoRepository afiliadoRepository;

    // ================= CADASTRO =================
    @PostMapping
    public Afiliado cadastrar(@RequestBody Afiliado afiliado) {
        return afiliadoRepository.save(afiliado);
    }

    // ================= LOGIN =================
    @PostMapping("/login")
    public Afiliado login(@RequestBody Afiliado dadosLogin) {

        Optional<Afiliado> afiliado =
                afiliadoRepository.findByEmailAndSenha(
                        dadosLogin.getEmail(),
                        dadosLogin.getSenha()
                );

        return afiliado.orElse(null);
    }
}
